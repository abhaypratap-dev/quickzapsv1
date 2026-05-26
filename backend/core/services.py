import base64
import json
import re
from decimal import Decimal, ROUND_HALF_UP
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from uuid import uuid4

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import (
    AepsMerchantProfile,
    AdminAPIMargin,
    AuditLog,
    BulkMessage,
    CommissionLedger,
    CommissionRule,
    FundRequest,
    KYCProfile,
    Notification,
    OnboardingApplication,
    Operator,
    Provider,
    ProviderWebhookEvent,
    Role,
    Scheme,
    Service,
    ServiceTransaction,
    User,
    UserSecurityPolicy,
    Wallet,
    WalletLedgerEntry,
)
from .fingpay_aeps import (
    FingpayAepsClient,
    compact_provider_response,
    fingpay_success,
    is_valid_aadhaar,
    mask_aadhaar,
    md5_hex,
    sanitize_payload,
)


MONEY_PLACES = Decimal("0.0001")


def money(value):
    return Decimal(value).quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)


def new_reference(prefix):
    return f"{prefix}{uuid4().hex[:16].upper()}"


def normalize_provider_status(value, default="pending"):
    normalized = str(value or "").strip().lower()
    mapping = {
        "success": "success",
        "successful": "success",
        "completed": "success",
        "paid": "success",
        "captured": "success",
        "approved": "success",
        "failed": "failed",
        "failure": "failed",
        "error": "failed",
        "declined": "failed",
        "rejected": "failed",
        "pending": "pending",
        "processing": "pending",
        "queued": "pending",
        "accepted": "pending",
        "created": "pending",
    }
    return mapping.get(normalized, default)


def provider_sandbox_enabled():
    return bool(getattr(settings, "PROVIDER_SANDBOX_MODE", True))


def provider_config(provider, key, default=None):
    if not provider or not isinstance(provider.config, dict):
        return default
    return provider.config.get(key, default)


def get_client_ip(request):
    if not request:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def user_has_permission(user, permission_code):
    if not user.is_authenticated or not user.role:
        return False
    permissions = user.role.permissions or []
    return "*" in permissions or permission_code in permissions


def scoped_user_queryset(actor):
    base = User.objects.select_related("role", "parent", "scheme", "service_package").all()
    if not actor.is_authenticated:
        return base.none()
    if actor.is_platform_admin:
        return base
    ids = descendant_ids(actor)
    return base.filter(Q(id=actor.id) | Q(id__in=ids))


def descendant_ids(user):
    discovered = set()
    frontier = [user.id]
    while frontier:
        child_ids = list(User.objects.filter(parent_id__in=frontier).values_list("id", flat=True))
        child_ids = [child_id for child_id in child_ids if child_id not in discovered]
        discovered.update(child_ids)
        frontier = child_ids
    return discovered


def assert_can_manage_user(actor, target):
    if actor.is_platform_admin:
        return
    if target.id == actor.id:
        return
    if target.id not in descendant_ids(actor):
        raise PermissionDenied("You can only manage your own downline users.")


def assert_can_create_role(actor, role):
    if actor.is_platform_admin:
        return
    if not actor.role or not actor.role.child_roles.filter(id=role.id).exists():
        raise PermissionDenied("This role cannot be created by your account.")


class AuditService:
    @staticmethod
    def log(actor, action, entity, before=None, after=None, request=None, metadata=None):
        entity_type = entity.__class__.__name__ if entity else "system"
        entity_id = str(getattr(entity, "id", "")) if entity else ""
        return AuditLog.objects.create(
            actor=actor if getattr(actor, "is_authenticated", False) else None,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before=before or {},
            after=after or {},
            ip_address=get_client_ip(request),
            metadata=metadata or {},
        )


class UserCreationService:
    @staticmethod
    @transaction.atomic
    def create_user(actor, data, request=None):
        role = data["role"]
        parent = data.get("parent")
        assert_can_create_role(actor, role)
        if parent:
            assert_can_manage_user(actor, parent)
            if not parent.role or not parent.role.child_roles.filter(id=role.id).exists():
                raise ValidationError({"role": "Selected parent cannot create this user role."})
        elif not role.is_admin_role:
            raise ValidationError({"parent": "Parent user is required for non-admin accounts."})

        username = data.get("username") or data["mobile"]
        status = data.get("status", "active")
        user = User(
            username=username,
            mobile=data["mobile"],
            email=data["email"],
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            role=role,
            parent=parent,
            status=status,
            is_active=status == "active",
            scheme=data.get("scheme"),
            service_package=data.get("service_package"),
            cap_balance=data.get("cap_balance", Decimal("0")),
            company_name=data.get("company_name", ""),
            business_type=data.get("business_type", ""),
            address=data.get("address", ""),
            city=data.get("city", ""),
            state=data.get("state", ""),
            pin_code=data.get("pin_code", ""),
            dob=data.get("dob"),
            pan_number=data.get("pan_number", ""),
            aadhaar_number=data.get("aadhaar_number", ""),
        )
        user.set_password(data["password"])
        if data.get("mpin"):
            user.mpin_hash = make_password(data["mpin"])
        if data.get("tpin"):
            user.tpin_hash = make_password(data["tpin"])
        user.save()
        Wallet.objects.create(user=user, cap_balance=user.cap_balance)
        UserSecurityPolicy.objects.create(
            user=user,
            transaction_tpin_required=data.get("transaction_tpin_required", True),
            login_sms_otp_enabled=data.get("login_sms_otp_enabled", False),
            login_email_otp_enabled=data.get("login_email_otp_enabled", False),
            login_whatsapp_otp_enabled=data.get("login_whatsapp_otp_enabled", False),
            login_mpin_enabled=data.get("login_mpin_enabled", False),
            aadhaar_kyc_required=data.get("aadhaar_kyc_required", True),
            pan_kyc_required=data.get("pan_kyc_required", True),
            cap_balance_enforced=data.get("cap_balance_enforced", False),
        )
        KYCProfile.objects.create(
            user=user,
            status=user.kyc_status,
            pan_number=user.pan_number,
            aadhaar_number=user.aadhaar_number,
        )
        AuditService.log(actor, "user.create", user, request=request, after={"mobile": user.mobile, "role": role.code})
        return user


class RoleUpgradeService:
    @staticmethod
    @transaction.atomic
    def upgrade(actor, user, new_role, scheme=None, request=None):
        assert_can_manage_user(actor, user)
        assert_can_create_role(actor, new_role)
        children = user.children.exclude(role__in=new_role.child_roles.all())
        if children.exists():
            raise ValidationError("Existing child users are not valid under the selected new role.")
        before = {"role": user.role.code if user.role else None, "scheme": user.scheme_id}
        user.role = new_role
        if scheme:
            user.scheme = scheme
        user.save(update_fields=["role", "scheme", "updated_at"])
        AuditService.log(actor, "user.role_upgrade", user, before=before, after={"role": new_role.code}, request=request)
        return user


class KYCSubmissionService:
    @staticmethod
    @transaction.atomic
    def submit(user, data, files=None, request=None):
        profile, _ = KYCProfile.objects.get_or_create(user=user)
        profile.pan_number = data.get("pan_number", profile.pan_number)
        profile.aadhaar_number = data.get("aadhaar_number", profile.aadhaar_number)
        file_map = ["aadhaar_front", "aadhaar_back", "pan_image", "shop_image", "user_photo"]
        files = files or {}
        for field in file_map:
            if field in files:
                setattr(profile, field, files[field])
        profile.status = "pending"
        profile.rejection_reason = ""
        profile.save()
        user.pan_number = profile.pan_number
        user.aadhaar_number = profile.aadhaar_number
        user.kyc_status = "pending"
        user.save(update_fields=["pan_number", "aadhaar_number", "kyc_status", "updated_at"])
        AuditService.log(user, "kyc.submit", profile, request=request)
        return profile


class KYCReviewService:
    @staticmethod
    @transaction.atomic
    def review(actor, profile, status, reason="", request=None):
        if not user_has_permission(actor, "kyc.approve") and not actor.is_platform_admin:
            raise PermissionDenied("KYC review permission is required.")
        if status not in {"approved", "rejected", "reupload_requested"}:
            raise ValidationError({"status": "Status must be approved, rejected, or reupload_requested."})
        before = {"status": profile.status}
        profile.status = status
        profile.reviewer = actor
        profile.reviewed_at = timezone.now()
        profile.rejection_reason = reason if status != "approved" else ""
        profile.save()
        profile.user.kyc_status = status
        profile.user.save(update_fields=["kyc_status", "updated_at"])
        AuditService.log(actor, "kyc.review", profile, before=before, after={"status": status, "reason": reason}, request=request)
        return profile


class OnboardingService:
    @staticmethod
    def _split_name(full_name):
        parts = [part for part in (full_name or "").strip().split(" ") if part]
        first = parts[0] if parts else ""
        last = " ".join(parts[1:]) if len(parts) > 1 else ""
        return first, last

    @staticmethod
    def eligible_parent_queryset(requested_role):
        role_codes = {
            "RETAILER": ["DBR", "SDBR"],
            "DBR": ["SDBR"],
            "SDBR": [],
        }.get(requested_role, [])
        return User.objects.select_related("role").filter(status="active", role__code__in=role_codes)

    @staticmethod
    def initial_status(application):
        if application.parent_id and not application.direct_to_admin:
            return "pending_parent"
        return "pending_admin"

    @staticmethod
    def validate_hierarchy(application):
        if application.requested_role == "SDBR":
            application.parent = None
            application.direct_to_admin = True
            return
        if application.parent_id:
            allowed = list(OnboardingService.eligible_parent_queryset(application.requested_role).values_list("id", flat=True))
            if application.parent_id not in allowed:
                raise ValidationError({"parent": "Selected parent is not valid for this onboarding role."})
            return
        if not application.direct_to_admin:
            raise ValidationError({"parent": "Select a parent or choose direct admin approval."})

    @staticmethod
    @transaction.atomic
    def prepare_application(application, request=None):
        from . import cashfree

        OnboardingService.validate_hierarchy(application)
        application.status = OnboardingService.initial_status(application)
        application.verification_mode = cashfree.mode_name()
        application.pan_verification = cashfree.verify_pan(application)
        application.aadhaar_verification = cashfree.create_digilocker_session(application)
        application.bank_verification = cashfree.create_reverse_penny_drop(application)
        application.gst_verification = cashfree.verify_gstin(application)
        application.udyam_verification = cashfree.verify_udyam(application)
        application.rpd_reference_id = application.bank_verification.get("ref_id", "")
        application.rpd_link = application.bank_verification.get("payment_link", "")
        application.rpd_status = application.bank_verification.get("rpd_status") or application.bank_verification.get("status", "")
        application.save()
        AuditService.log(application.submitted_by, "onboarding.submit", application, request=request)
        return application

    @staticmethod
    def can_parent_review(actor, application):
        return bool(application.parent_id and actor.id == application.parent_id and application.status == "pending_parent")

    @staticmethod
    def can_admin_review(actor):
        return bool(actor.is_platform_admin or user_has_permission(actor, "onboarding.approve"))

    @staticmethod
    @transaction.atomic
    def approve(actor, application, note="", request=None):
        if application.status == "pending_parent" and OnboardingService.can_parent_review(actor, application):
            application.status = "pending_admin"
            application.parent_approved_by = actor
            application.review_note = note
            application.save(update_fields=["status", "parent_approved_by", "review_note", "updated_at"])
            AuditService.log(actor, "onboarding.parent.approve", application, request=request, metadata={"note": note})
            return application

        if application.status != "pending_admin":
            raise ValidationError({"status": "Only pending applications can be approved."})
        if not OnboardingService.can_admin_review(actor):
            raise PermissionDenied("Admin onboarding approval permission is required.")

        user = OnboardingService.create_user_from_application(actor, application, request=request)
        application.status = "created"
        application.created_user = user
        application.approved_by = actor
        application.approved_at = timezone.now()
        application.review_note = note
        application.save(update_fields=["status", "created_user", "approved_by", "approved_at", "review_note", "updated_at"])
        AuditService.log(actor, "onboarding.admin.approve", application, request=request, metadata={"created_user": user.id, "note": note})
        return application

    @staticmethod
    @transaction.atomic
    def reject(actor, application, note="", request=None):
        if application.status not in {"pending_parent", "pending_admin"}:
            raise ValidationError({"status": "Only pending applications can be rejected."})
        if application.status == "pending_parent" and not OnboardingService.can_parent_review(actor, application):
            raise PermissionDenied("Only the selected parent can reject this application at parent review.")
        if application.status == "pending_admin" and not OnboardingService.can_admin_review(actor):
            raise PermissionDenied("Admin onboarding approval permission is required.")
        application.status = "rejected"
        application.review_note = note
        application.rejected_at = timezone.now()
        application.save(update_fields=["status", "review_note", "rejected_at", "updated_at"])
        AuditService.log(actor, "onboarding.reject", application, request=request, metadata={"note": note})
        return application

    @staticmethod
    @transaction.atomic
    def create_user_from_application(actor, application, request=None):
        if application.created_user_id:
            return application.created_user
        if User.objects.filter(mobile=application.mobile).exists():
            raise ValidationError({"mobile": "A user with this mobile number already exists."})
        if User.objects.filter(email=application.email).exists():
            raise ValidationError({"email": "A user with this email already exists."})

        role = Role.objects.get(code=application.requested_role, active=True)
        parent = application.parent
        if not parent and application.requested_role != "SDBR":
            parent = actor if actor.is_platform_admin else None

        first_name, last_name = OnboardingService._split_name(application.full_name)
        user = User(
            username=application.mobile,
            mobile=application.mobile,
            email=application.email,
            first_name=first_name,
            last_name=last_name,
            role=role,
            parent=parent,
            status="active",
            is_active=True,
            kyc_status="approved",
            company_name=application.business_name,
            business_type=application.business_type,
            address=application.business_address,
            city=application.city,
            state=application.state,
            pin_code=application.pin_code,
            dob=application.dob,
            pan_number=application.pan_number,
            aadhaar_number=application.aadhaar_number,
        )
        user.set_password(getattr(settings, "ONBOARDING_DEFAULT_PASSWORD", "Demo@12345"))
        user.save()
        Wallet.objects.create(user=user, cap_balance=user.cap_balance)
        UserSecurityPolicy.objects.create(user=user, aadhaar_kyc_required=True, pan_kyc_required=True)
        KYCProfile.objects.create(
            user=user,
            status="approved",
            pan_number=user.pan_number,
            aadhaar_number=user.aadhaar_number,
            shop_image=application.shop_photo,
            user_photo=application.live_photo,
            reviewer=actor,
            reviewed_at=timezone.now(),
        )
        return user


class AepsMerchantService:
    TRANSACTION_SERVICE_CODES = {
        "CW": "AEPS_CASH_WITHDRAWAL",
        "BE": "AEPS_BALANCE_ENQUIRY",
        "MS": "AEPS_MINI_STATEMENT",
        "M": "AADHAAR_PAY",
        "CD": "AEPS_CASH_DEPOSIT",
    }
    TRANSACTION_LABELS = {
        "CW": "Cash Withdrawal",
        "BE": "Balance Enquiry",
        "MS": "Mini Statement",
        "M": "Aadhaar Pay",
        "CD": "Cash Deposit",
    }
    PENDING_RESPONSE_CODES = {"91", "52", "08", "FP009"}

    @staticmethod
    def _source_application(user):
        try:
            return user.source_onboarding_application
        except OnboardingApplication.DoesNotExist:
            return None

    @staticmethod
    def _kyc_profile(user):
        try:
            return user.kyc_profile
        except KYCProfile.DoesNotExist:
            return None

    @staticmethod
    def _split_name(user):
        full_name = (user.get_full_name() or user.company_name or user.mobile or "").strip()
        parts = [part for part in full_name.split(" ") if part]
        first = parts[0] if parts else "Merchant"
        last = " ".join(parts[1:]) if len(parts) > 1 else "User"
        return first[:40], last[:40]

    @staticmethod
    def _safe_login_id(user):
        raw = f"QZ{user.mobile}"
        login_id = "".join(ch for ch in raw.upper() if ch.isalnum())
        return login_id[:40] or f"QZ{user.id}"

    @staticmethod
    def _file_to_base64(file_field):
        if not file_field:
            return ""
        try:
            if not file_field.name:
                return ""
            with file_field.open("rb") as handle:
                return base64.b64encode(handle.read()).decode("ascii")
        except (OSError, ValueError):
            return ""

    @staticmethod
    def _aadhaar_for(user, data):
        aadhaar = data.get("aadhaar_number") or getattr(user, "aadhaar_number", "")
        aadhaar = "".join(ch for ch in str(aadhaar or "") if ch.isdigit())
        if not aadhaar:
            raise ValidationError({"aadhaar_number": "Aadhaar number is required for Fingpay AEPS."})
        if not is_valid_aadhaar(aadhaar):
            raise ValidationError({"aadhaar_number": "Aadhaar number failed checksum validation."})
        return aadhaar

    @staticmethod
    def _pan_for(user, data):
        pan = str(data.get("pan_number") or getattr(user, "pan_number", "") or "").strip().upper()
        if not pan:
            raise ValidationError({"pan_number": "PAN number is required for Fingpay AEPS."})
        if not re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", pan):
            raise ValidationError({"pan_number": "Enter a valid PAN."})
        return pan

    @staticmethod
    def prefill(user):
        source = AepsMerchantService._source_application(user)
        kyc = AepsMerchantService._kyc_profile(user)
        first_name, last_name = AepsMerchantService._split_name(user)
        address = user.address or getattr(source, "business_address", "") or ""
        city = user.city or getattr(source, "city", "") or ""
        state = user.state or getattr(source, "state", "") or ""
        pin_code = user.pin_code or getattr(source, "pin_code", "") or ""
        company_name = user.company_name or getattr(source, "business_name", "") or user.get_full_name() or user.mobile
        bank_account = getattr(source, "account_number", "") or ""
        pan_number = user.pan_number or getattr(kyc, "pan_number", "") or getattr(source, "pan_number", "")
        aadhaar_number = user.aadhaar_number or getattr(kyc, "aadhaar_number", "") or getattr(source, "aadhaar_number", "")
        return {
            "merchant_login_id": AepsMerchantService._safe_login_id(user),
            "merchant_phone_number": user.mobile,
            "first_name": first_name,
            "last_name": last_name,
            "merchant_address1": address[:120],
            "merchant_address2": " ".join(part for part in [city, state, pin_code] if part)[:120] or address[:120],
            "merchant_state": getattr(settings, "FINGPAY_AEPS_DEFAULT_STATE_CODE", 9),
            "merchant_city_name": city,
            "merchant_district_name": city,
            "merchant_pin_code": pin_code,
            "company_legal_name": company_name,
            "company_type": getattr(settings, "FINGPAY_AEPS_DEFAULT_COMPANY_TYPE", 2),
            "email_id": user.email,
            "pan_number": pan_number,
            "aadhaar_masked": mask_aadhaar(aadhaar_number),
            "has_aadhaar": bool(aadhaar_number),
            "gstin_number": getattr(source, "gst_number", ""),
            "bank_account_number": bank_account,
            "bank_ifsc_code": getattr(source, "ifsc", ""),
            "company_bank_name": getattr(source, "bank_name", ""),
            "bank_account_name": getattr(source, "account_holder_name", "") or company_name,
            "device_imei": getattr(settings, "FINGPAY_AEPS_DEFAULT_DEVICE_IMEI", ""),
            "latitude": getattr(settings, "FINGPAY_AEPS_DEFAULT_LATITUDE", "28.6139000"),
            "longitude": getattr(settings, "FINGPAY_AEPS_DEFAULT_LONGITUDE", "77.2090000"),
        }

    @staticmethod
    def get_profile_payload(user):
        try:
            profile = user.aeps_profile
        except AepsMerchantProfile.DoesNotExist:
            profile = None
        return {
            "profile": profile,
            "prefill": AepsMerchantService.prefill(user),
            "can_access_services": bool(profile and profile.can_access_services),
            "next_step": profile.next_step if profile else "merchant_onboarding",
            "dummy_mode": bool(getattr(settings, "FINGPAY_AEPS_DUMMY_MODE", True)),
            "base_url": getattr(settings, "FINGPAY_AEPS_BASE_URL", "https://fingpayap.tapits.in"),
        }

    @staticmethod
    def _onboarding_payload(user, data, request=None):
        client = FingpayAepsClient()
        kyc = AepsMerchantService._kyc_profile(user)
        source = AepsMerchantService._source_application(user)
        aadhaar = AepsMerchantService._aadhaar_for(user, data)
        pan = AepsMerchantService._pan_for(user, data)
        latitude = str(data.get("latitude") or getattr(settings, "FINGPAY_AEPS_DEFAULT_LATITUDE", "28.6139000"))
        longitude = str(data.get("longitude") or getattr(settings, "FINGPAY_AEPS_DEFAULT_LONGITUDE", "77.2090000"))
        bank_account = str(data.get("bank_account_number") or getattr(source, "account_number", "") or "")

        pan_image = data.get("merchant_pan_image_base64") or AepsMerchantService._file_to_base64(getattr(kyc, "pan_image", None))
        aadhaar_image = data.get("masked_aadhaar_image_base64") or AepsMerchantService._file_to_base64(getattr(kyc, "aadhaar_front", None))
        shop_image = data.get("background_image_of_shop_base64") or AepsMerchantService._file_to_base64(getattr(kyc, "shop_image", None))

        return {
            "username": client.super_login_id,
            "password": md5_hex(client.super_password),
            "ipAddress": get_client_ip(request) or "127.0.0.1",
            "latitude": latitude,
            "longitude": longitude,
            "supermerchantId": client.super_merchant_id,
            "merchant": {
                "merchantLoginId": data["merchant_login_id"],
                "merchantLoginPin": data["merchant_pin"],
                "firstName": data["first_name"],
                "lastName": data["last_name"],
                "middleName": data.get("middle_name", ""),
                "merchantPhoneNumber": data["merchant_phone_number"],
                "merchantAddress": {
                    "merchantAddress1": data["merchant_address1"],
                    "merchantAddress2": data["merchant_address2"],
                    "merchantState": data["merchant_state"],
                    "merchantCityName": data["merchant_city_name"],
                    "merchantDistrictName": data["merchant_district_name"],
                    "merchantPinCode": data["merchant_pin_code"],
                },
                "companyLegalName": data["company_legal_name"],
                "userType": data.get("user_type", "merchant"),
                "companyType": data["company_type"],
                "emailId": data.get("email_id") or user.email,
                "certificateOfIncorporationImage": data.get("certificate_of_incorporation_image", "False"),
                "kyc": {
                    "userPan": pan,
                    "aadhaarNumber": aadhaar,
                    "gstinNumber": data.get("gstin_number", ""),
                    "companyOrShopPan": data.get("company_or_shop_pan") or pan,
                    "merchantPanImage": pan_image,
                    "maskedAadharImage": aadhaar_image,
                    "shopAndPanImage": data.get("shop_and_pan_image", "True"),
                },
                "settlementV1": {
                    "companyBankAccountNumber": bank_account,
                    "bankIfscCode": data["bank_ifsc_code"],
                    "companyBankName": data["company_bank_name"],
                    "bankAccountName": data["bank_account_name"],
                },
                "tradeBusinessProof": data.get("trade_business_proof", "True"),
                "termsConditionCheck": data.get("terms_condition_check", "True"),
                "cancelledChequeImages": data.get("cancelled_cheque_images", "True"),
                "physicalVerification": data.get("physical_verification", "True"),
                "videoKycWithLatLongData": data.get("video_kyc_with_lat_long_data", "True"),
                "merchantKycAddressData": {
                    "shopAddress": data.get("shop_address") or data["merchant_address1"],
                    "shopCity": data.get("shop_city") or data["merchant_city_name"],
                    "shopDistrict": data.get("shop_district") or data["merchant_district_name"],
                    "shopState": data.get("shop_state") or data["merchant_state"],
                    "shopPincode": data.get("shop_pin_code") or data["merchant_pin_code"],
                    "shopLatitude": latitude,
                    "shopLongitude": longitude,
                    "backgroundImageOfShop": shop_image,
                },
            },
        }

    @staticmethod
    def onboard(user, data, request=None):
        existing = AepsMerchantProfile.objects.filter(merchant_login_id=data["merchant_login_id"]).exclude(user=user).first()
        if existing:
            raise ValidationError({"merchant_login_id": "This merchant login ID is already linked to another user."})

        client = FingpayAepsClient()
        payload = AepsMerchantService._onboarding_payload(user, data, request=request)
        bank_account = str(data.get("bank_account_number") or "")
        profile, _ = AepsMerchantProfile.objects.get_or_create(
            user=user,
            defaults={
                "merchant_login_id": data["merchant_login_id"],
                "merchant_phone_number": data["merchant_phone_number"],
                "super_merchant_id": client.super_merchant_id,
            },
        )
        profile.merchant_login_id = data["merchant_login_id"]
        profile.merchant_phone_number = data["merchant_phone_number"]
        profile.super_merchant_id = client.super_merchant_id
        profile.status = "onboarding_pending"
        profile.kyc_status = profile.kyc_status if profile.kyc_status != "failed" else "not_started"
        profile.device_imei = data.get("device_imei", profile.device_imei)
        profile.latitude = data.get("latitude") or None
        profile.longitude = data.get("longitude") or None
        profile.merchant_state = data["merchant_state"]
        profile.merchant_city_name = data["merchant_city_name"]
        profile.merchant_district_name = data["merchant_district_name"]
        profile.merchant_pin_code = data["merchant_pin_code"]
        profile.company_legal_name = data["company_legal_name"]
        profile.company_type = data["company_type"]
        profile.company_bank_name = data["company_bank_name"]
        profile.bank_ifsc_code = data["bank_ifsc_code"]
        profile.settlement_account_last4 = bank_account[-4:]
        profile.bank_account_name = data["bank_account_name"]
        profile.save()

        response = client.onboard_merchant(payload)
        safe_response = compact_provider_response(response)
        success = fingpay_success(response) and bool((response.get("data") or {}).get("merchantStatus", True))
        profile.fingpay_merchant_status = success
        profile.status = "onboarded" if success else "rejected"
        profile.onboarding_response = safe_response
        profile.last_provider_message = str(response.get("message") or (response.get("data") or {}).get("remarks") or "")[:240]
        profile.rejection_reason = "" if success else profile.last_provider_message
        if success:
            profile.last_onboarded_at = timezone.now()
        profile.save()
        AuditService.log(
            user,
            "aeps.merchant.onboard",
            profile,
            request=request,
            metadata={"request": sanitize_payload(payload), "response": safe_response, "success": success},
        )
        if not success:
            raise ValidationError({"code": "AEPS_ONBOARDING_FAILED", "message": profile.last_provider_message or "Fingpay merchant onboarding failed."})
        return profile

    @staticmethod
    def _active_profile(user, require_services=False):
        try:
            profile = user.aeps_profile
        except AepsMerchantProfile.DoesNotExist as exc:
            raise ValidationError({"code": "AEPS_ONBOARDING_REQUIRED", "message": "Complete AEPS merchant onboarding first."}) from exc
        if require_services and not profile.can_access_services:
            raise ValidationError({"code": "AEPS_KYC_REQUIRED", "message": "Complete AEPS merchant KYC before using AEPS services."})
        if profile.status in {"rejected", "suspended"}:
            raise ValidationError({"code": "AEPS_PROFILE_BLOCKED", "message": profile.rejection_reason or "AEPS merchant profile is not active."})
        return profile

    @staticmethod
    def send_ekyc_otp(user, data, request=None):
        profile = AepsMerchantService._active_profile(user)
        aadhaar = AepsMerchantService._aadhaar_for(user, data)
        pan = AepsMerchantService._pan_for(user, data)
        client = FingpayAepsClient()
        payload = {
            "superMerchantId": profile.super_merchant_id or client.super_merchant_id,
            "merchantLoginId": profile.merchant_login_id,
            "transactionType": "EKY",
            "mobileNumber": data.get("mobile_number") or profile.merchant_phone_number,
            "aadharNumber": aadhaar,
            "panNumber": pan,
            "matmSerialNumber": data.get("matm_serial_number", ""),
            "latitude": float(data.get("latitude") or profile.latitude or getattr(settings, "FINGPAY_AEPS_DEFAULT_LATITUDE", "28.6139000")),
            "longitude": float(data.get("longitude") or profile.longitude or getattr(settings, "FINGPAY_AEPS_DEFAULT_LONGITUDE", "77.2090000")),
        }
        response = client.send_ekyc_otp(payload, device_imei=data.get("device_imei") or profile.device_imei)
        success = fingpay_success(response)
        response_data = response.get("data") if isinstance(response.get("data"), dict) else {}
        if success:
            profile.kyc_status = "otp_sent"
            profile.primary_key_id = response_data.get("primaryKeyId") or profile.primary_key_id
            profile.encode_fp_txn_id = response_data.get("encodeFPTxnId") or profile.encode_fp_txn_id
        else:
            profile.kyc_status = "failed"
        profile.ekyc_response = compact_provider_response(response)
        profile.last_provider_message = str(response.get("message") or "")[:240]
        profile.save()
        AuditService.log(user, "aeps.ekyc.otp.send", profile, request=request, metadata={"request": sanitize_payload(payload), "response": profile.ekyc_response})
        if not success:
            raise ValidationError({"code": "AEPS_EKYC_OTP_FAILED", "message": profile.last_provider_message or "Unable to send AEPS KYC OTP."})
        return profile, response

    @staticmethod
    def validate_ekyc_otp(user, data, request=None):
        profile = AepsMerchantService._active_profile(user)
        client = FingpayAepsClient()
        primary_key_id = data.get("primary_key_id") or profile.primary_key_id
        encode_fp_txn_id = data.get("encode_fp_txn_id") or profile.encode_fp_txn_id
        if not primary_key_id or not encode_fp_txn_id:
            raise ValidationError({"code": "AEPS_EKYC_SESSION_REQUIRED", "message": "Send AEPS KYC OTP before validating it."})
        payload = {
            "superMerchantId": profile.super_merchant_id or client.super_merchant_id,
            "merchantLoginId": profile.merchant_login_id,
            "otp": data["otp"],
            "primaryKeyId": primary_key_id,
            "encodeFPTxnId": encode_fp_txn_id,
        }
        response = client.validate_ekyc_otp(payload, device_imei=data.get("device_imei") or profile.device_imei)
        success = fingpay_success(response)
        response_data = response.get("data") if isinstance(response.get("data"), dict) else {}
        if success:
            profile.kyc_status = "otp_validated"
            profile.primary_key_id = response_data.get("primaryKeyId") or profile.primary_key_id
            profile.encode_fp_txn_id = response_data.get("encodeFPTxnId") or profile.encode_fp_txn_id
            status_response = client.ekyc_status({"superMerchantId": profile.super_merchant_id or client.super_merchant_id, "merchantLoginId": profile.merchant_login_id})
            if fingpay_success(status_response):
                profile.kyc_status = "verified"
                profile.status = "active"
                profile.last_ekyc_at = timezone.now()
                profile.ekyc_response = compact_provider_response(status_response)
            else:
                profile.ekyc_response = compact_provider_response(response)
        else:
            profile.kyc_status = "failed"
            profile.ekyc_response = compact_provider_response(response)
        profile.last_provider_message = str(response.get("message") or "")[:240]
        profile.save()
        AuditService.log(user, "aeps.ekyc.otp.validate", profile, request=request, metadata={"response": profile.ekyc_response, "success": success})
        if not success:
            raise ValidationError({"code": "AEPS_EKYC_VALIDATE_FAILED", "message": profile.last_provider_message or "AEPS KYC OTP validation failed."})
        return profile, response

    @staticmethod
    def biometric_ekyc(user, data, request=None):
        profile = AepsMerchantService._active_profile(user)
        aadhaar = AepsMerchantService._aadhaar_for(user, data)
        client = FingpayAepsClient()
        primary_key_id = data.get("primary_key_id") or profile.primary_key_id
        encode_fp_txn_id = data.get("encode_fp_txn_id") or profile.encode_fp_txn_id
        if not primary_key_id or not encode_fp_txn_id:
            raise ValidationError({"code": "AEPS_EKYC_SESSION_REQUIRED", "message": "Send AEPS KYC OTP before biometric KYC."})
        payload = {
            "superMerchantId": profile.super_merchant_id or client.super_merchant_id,
            "merchantLoginId": profile.merchant_login_id,
            "primaryKeyId": primary_key_id,
            "encodeFPTxnId": encode_fp_txn_id,
            "requestRemarks": data.get("request_remarks", "AEPS KYC"),
            "cardnumberORUID": {
                "nationalBankIdentificationNumber": data.get("bank_iin") or None,
                "indicatorforUID": int(data.get("indicator_for_uid", 0)),
                "adhaarNumber": aadhaar,
            },
            "captureResponse": data["capture_response"],
        }
        response = client.biometric_ekyc(payload, device_imei=data.get("device_imei") or profile.device_imei)
        success = fingpay_success(response)
        profile.kyc_status = "verified" if success else "failed"
        if success:
            profile.status = "active"
            profile.last_ekyc_at = timezone.now()
        profile.ekyc_response = compact_provider_response(response)
        profile.last_provider_message = str(response.get("message") or "")[:240]
        profile.save()
        AuditService.log(user, "aeps.ekyc.biometric", profile, request=request, metadata={"request": sanitize_payload(payload), "response": profile.ekyc_response})
        if not success:
            raise ValidationError({"code": "AEPS_EKYC_BIOMETRIC_FAILED", "message": profile.last_provider_message or "AEPS biometric KYC failed."})
        return profile, response

    @staticmethod
    def refresh_ekyc_status(user, request=None):
        profile = AepsMerchantService._active_profile(user)
        client = FingpayAepsClient()
        payload = {"superMerchantId": profile.super_merchant_id or client.super_merchant_id, "merchantLoginId": profile.merchant_login_id}
        response = client.ekyc_status(payload)
        success = fingpay_success(response)
        if success:
            profile.status = "active"
            profile.kyc_status = "verified"
            profile.last_ekyc_at = timezone.now()
        profile.ekyc_response = compact_provider_response(response)
        profile.last_provider_message = str(response.get("message") or "")[:240]
        profile.save()
        AuditService.log(user, "aeps.ekyc.status", profile, request=request, metadata={"response": profile.ekyc_response, "success": success})
        return profile, response

    @staticmethod
    def _transaction_status(response):
        data = response.get("data") if isinstance(response, dict) and isinstance(response.get("data"), dict) else {}
        response_code = str(data.get("responseCode") or data.get("transactionStatusCode") or "")
        bank_rrn = data.get("bankRRN") or data.get("bankRrn") or data.get("rrn")
        if response_code == "00" and bank_rrn:
            return "success"
        if response_code in AepsMerchantService.PENDING_RESPONSE_CODES:
            return "pending"
        if response.get("status") is False:
            return "failed"
        return "pending"

    @staticmethod
    def execute_transaction(user, data, request=None):
        profile = AepsMerchantService._active_profile(user, require_services=True)
        if profile.user.kyc_status != "approved":
            raise ValidationError({"code": "KYC_REQUIRED", "message": "QuickZaps KYC approval is required for AEPS."})
        transaction_type = data["transaction_type"]
        service_code = AepsMerchantService.TRANSACTION_SERVICE_CODES[transaction_type]
        try:
            service = Service.objects.get(code=service_code, active=True)
        except Service.DoesNotExist as exc:
            raise ValidationError({"service": f"{service_code} is not configured or inactive."}) from exc
        amount = money(data.get("amount") or Decimal("0"))
        if amount < service.min_amount or amount > service.max_amount:
            raise ValidationError({"amount": f"Amount must be between {service.min_amount} and {service.max_amount}."})
        aadhaar = AepsMerchantService._aadhaar_for(user, data)
        merchant_pin_hash = md5_hex(data["merchant_pin"])
        reference = data.get("merchant_transaction_id") or new_reference("AEPS")
        existing = ServiceTransaction.objects.filter(initiated_by=user, idempotency_key=reference).first()
        if existing:
            return existing, existing.response_payload
        provider = Provider.objects.filter(provider_type="aeps", active=True, health_status="healthy").first()
        if not provider:
            raise ValidationError({"code": "AEPS_PROVIDER_UNAVAILABLE", "message": "No healthy AEPS provider route is configured."})

        client = FingpayAepsClient()
        capture_response = data.get("capture_response") or {}
        payload = {
            "cardnumberORUID": {
                "adhaarNumber": aadhaar,
                "indicatorforUID": int(data.get("indicator_for_uid", 0)),
                "nationalBankIdentificationNumber": data["bank_iin"],
            },
            "mobileNumber": data["customer_mobile"],
            "paymentType": "B",
            "timestamp": timezone.localtime().strftime("%d/%m/%Y %H:%M:%S"),
            "transactionType": transaction_type,
            "latitude": float(data.get("latitude") or profile.latitude or getattr(settings, "FINGPAY_AEPS_DEFAULT_LATITUDE", "28.6139000")),
            "longitude": float(data.get("longitude") or profile.longitude or getattr(settings, "FINGPAY_AEPS_DEFAULT_LONGITUDE", "77.2090000")),
            "requestRemarks": data.get("request_remarks", AepsMerchantService.TRANSACTION_LABELS[transaction_type]),
            "deviceTransactionId": data.get("device_transaction_id", reference),
            "captureResponse": capture_response,
            "languageCode": data.get("language_code", "en"),
            "transactionAmount": float(amount),
            "merchantUserName": profile.merchant_login_id,
            "merchantPin": merchant_pin_hash.upper(),
            "superMerchantId": str(profile.super_merchant_id or client.super_merchant_id),
        }
        if transaction_type == "CW":
            payload["merchantTranId"] = reference
        else:
            payload["merchantTransactionId"] = reference

        tx = ServiceTransaction.objects.create(
            reference=reference,
            initiated_by=user,
            service=service,
            provider=provider,
            customer_mobile=data["customer_mobile"],
            amount=amount,
            charge=Decimal("0.0000"),
            commission=Decimal("0.0000"),
            admin_margin=Decimal("0.0000"),
            total_debit=Decimal("0.0000"),
            status="pending",
            idempotency_key=reference,
            request_payload=sanitize_payload(payload),
            description=AepsMerchantService.TRANSACTION_LABELS[transaction_type],
        )
        response = client.execute_product(transaction_type, payload, device_imei=data.get("device_imei") or profile.device_imei)
        safe_response = compact_provider_response(response)
        response_data = response.get("data") if isinstance(response.get("data"), dict) else {}
        tx.status = AepsMerchantService._transaction_status(response)
        tx.provider_status = str(response_data.get("responseCode") or response_data.get("transactionStatusCode") or response.get("statusCode") or "")
        tx.provider_reference = (
            response_data.get("fpTransactionId")
            or response_data.get("FingpayTransactionId")
            or response_data.get("fingpayTransactionId")
            or response_data.get("bankRRN")
            or response_data.get("bankRrn")
            or ""
        )
        tx.response_payload = safe_response
        tx.save(update_fields=["status", "provider_status", "provider_reference", "response_payload", "updated_at"])
        AuditService.log(user, "aeps.transaction.execute", tx, request=request, metadata={"request": tx.request_payload, "response": safe_response})
        return tx, safe_response


class WalletLedgerService:
    @staticmethod
    def _locked_wallet(user_or_wallet):
        wallet_id = user_or_wallet.id if isinstance(user_or_wallet, Wallet) else user_or_wallet.wallet.id
        return Wallet.objects.select_for_update().get(id=wallet_id)

    @staticmethod
    @transaction.atomic
    def credit(user, amount, entry_type="credit", transaction_obj=None, reference="", remarks="", actor=None, metadata=None):
        amount = money(amount)
        wallet = WalletLedgerService._locked_wallet(user)
        opening = wallet.available_balance
        wallet.available_balance = money(wallet.available_balance + amount)
        wallet.save(update_fields=["available_balance", "updated_at"])
        return WalletLedgerEntry.objects.create(
            wallet=wallet,
            user=user,
            transaction=transaction_obj,
            entry_type=entry_type,
            amount=amount,
            opening_balance=opening,
            closing_balance=wallet.available_balance,
            transaction_ref=reference,
            remarks=remarks,
            created_by=actor,
            metadata=metadata or {},
        )

    @staticmethod
    @transaction.atomic
    def debit(user, amount, entry_type="debit", transaction_obj=None, reference="", remarks="", actor=None, metadata=None):
        amount = money(amount)
        wallet = WalletLedgerService._locked_wallet(user)
        if wallet.available_balance < amount:
            raise ValidationError(
                {
                    "code": "INSUFFICIENT_BALANCE",
                    "available_balance": str(wallet.available_balance),
                    "required_amount": str(amount),
                }
            )
        opening = wallet.available_balance
        wallet.available_balance = money(wallet.available_balance - amount)
        wallet.save(update_fields=["available_balance", "updated_at"])
        return WalletLedgerEntry.objects.create(
            wallet=wallet,
            user=user,
            transaction=transaction_obj,
            entry_type=entry_type,
            amount=amount,
            opening_balance=opening,
            closing_balance=wallet.available_balance,
            transaction_ref=reference,
            remarks=remarks,
            created_by=actor,
            metadata=metadata or {},
        )

    @staticmethod
    @transaction.atomic
    def place_hold(user, amount, transaction_obj, reference="", remarks="Transaction hold"):
        amount = money(amount)
        wallet = WalletLedgerService._locked_wallet(user)
        if wallet.available_balance < amount:
            raise ValidationError(
                {
                    "code": "INSUFFICIENT_BALANCE",
                    "available_balance": str(wallet.available_balance),
                    "required_amount": str(amount),
                }
            )
        opening = wallet.available_balance
        wallet.available_balance = money(wallet.available_balance - amount)
        wallet.hold_balance = money(wallet.hold_balance + amount)
        wallet.save(update_fields=["available_balance", "hold_balance", "updated_at"])
        return WalletLedgerEntry.objects.create(
            wallet=wallet,
            user=user,
            transaction=transaction_obj,
            entry_type="hold",
            amount=amount,
            opening_balance=opening,
            closing_balance=wallet.available_balance,
            transaction_ref=reference,
            remarks=remarks,
        )

    @staticmethod
    @transaction.atomic
    def capture_hold(user, amount, transaction_obj, reference="", remarks="Provider success"):
        amount = money(amount)
        wallet = WalletLedgerService._locked_wallet(user)
        if wallet.hold_balance < amount:
            raise ValidationError({"hold_balance": "Hold balance is not sufficient."})
        opening = wallet.available_balance
        wallet.hold_balance = money(wallet.hold_balance - amount)
        wallet.save(update_fields=["hold_balance", "updated_at"])
        return WalletLedgerEntry.objects.create(
            wallet=wallet,
            user=user,
            transaction=transaction_obj,
            entry_type="hold_capture",
            amount=amount,
            opening_balance=opening,
            closing_balance=wallet.available_balance,
            transaction_ref=reference,
            remarks=remarks,
        )

    @staticmethod
    @transaction.atomic
    def release_hold(user, amount, transaction_obj, reference="", remarks="Provider failure"):
        amount = money(amount)
        wallet = WalletLedgerService._locked_wallet(user)
        if wallet.hold_balance < amount:
            raise ValidationError({"hold_balance": "Hold balance is not sufficient."})
        opening = wallet.available_balance
        wallet.hold_balance = money(wallet.hold_balance - amount)
        wallet.available_balance = money(wallet.available_balance + amount)
        wallet.save(update_fields=["available_balance", "hold_balance", "updated_at"])
        return WalletLedgerEntry.objects.create(
            wallet=wallet,
            user=user,
            transaction=transaction_obj,
            entry_type="hold_release",
            amount=amount,
            opening_balance=opening,
            closing_balance=wallet.available_balance,
            transaction_ref=reference,
            remarks=remarks,
        )


class FundRequestService:
    @staticmethod
    @transaction.atomic
    def review(actor, fund_request, status, note="", request=None):
        if not actor.is_platform_admin and not user_has_permission(actor, "wallet.fund.approve"):
            raise PermissionDenied("Fund approval permission is required.")
        if fund_request.status != "pending":
            raise ValidationError("Only pending fund requests can be reviewed.")
        fund_request.status = status
        fund_request.reviewed_by = actor
        fund_request.reviewed_at = timezone.now()
        fund_request.review_note = note
        fund_request.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_note", "updated_at"])
        if status == "approved":
            WalletLedgerService.credit(
                fund_request.user,
                fund_request.amount,
                entry_type="credit",
                reference=f"FUND-{fund_request.id}",
                remarks="Approved fund request",
                actor=actor,
            )
        AuditService.log(actor, "fund_request.review", fund_request, request=request, after={"status": status})
        return fund_request


class CommissionCalculator:
    @staticmethod
    def _value(amount, value, value_type):
        amount = money(amount)
        value = money(value)
        if value_type == "percent":
            return money(amount * value / Decimal("100"))
        return value

    @staticmethod
    def quote(user, service, operator, amount, provider=None):
        rule = None
        if user.scheme:
            rule = (
                CommissionRule.objects.filter(scheme=user.scheme, service=service, active=True)
                .filter(Q(operator=operator) | Q(operator__isnull=True))
                .order_by("-operator_id")
                .first()
            )
        commission = Decimal("0.0000")
        surcharge = Decimal("0.0000")
        tds = Decimal("0.0000")
        gst = Decimal("0.0000")
        if rule:
            commission = CommissionCalculator._value(amount, rule.commission_value, rule.commission_type)
            surcharge = CommissionCalculator._value(amount, rule.surcharge_value, rule.surcharge_type)
            tds = money(commission * rule.tds_percent / Decimal("100"))
            gst = money(surcharge * rule.gst_percent / Decimal("100"))

        admin_margin = Decimal("0.0000")
        if provider:
            margin = (
                AdminAPIMargin.objects.filter(service=service, provider=provider, active=True)
                .filter(Q(operator=operator) | Q(operator__isnull=True))
                .order_by("-operator_id")
                .first()
            )
            if margin:
                admin_margin = CommissionCalculator._value(amount, margin.margin_value, margin.margin_type)

        net_commission = money(max(Decimal("0.0000"), commission - tds))
        charge = money(surcharge + gst)
        return {
            "commission": net_commission,
            "gross_commission": money(commission),
            "tds": tds,
            "surcharge": surcharge,
            "gst": gst,
            "charge": charge,
            "admin_margin": money(admin_margin),
            "total_debit": money(amount + charge),
        }


class ProviderRouter:
    @staticmethod
    def provider_for(service):
        provider_type_map = {
            "billpay": "utility",
            "recharge": "recharge",
            "dmt": "dmt",
            "express_money": "dmt",
            "payout": "payout",
            "account_verify": "verification",
            "aeps": "aeps",
        }
        provider_type = provider_type_map.get(service.category, "utility")
        provider = Provider.objects.filter(provider_type=provider_type, active=True, health_status="healthy").first()
        if not provider:
            raise ValidationError({"code": "PROVIDER_UNAVAILABLE", "message": "No healthy provider route is configured."})
        return provider


class ProviderExecutionService:
    @staticmethod
    def _provider_reference(provider, prefix="QZ"):
        provider_key = "".join(ch for ch in (provider.code if provider else prefix) if ch.isalnum()).upper()[:8] or prefix
        return f"{provider_key}-{uuid4().hex[:12].upper()}"

    @staticmethod
    def _build_transaction_payload(transaction_obj):
        return {
            "reference": transaction_obj.reference,
            "idempotency_key": transaction_obj.idempotency_key,
            "service": transaction_obj.service.code,
            "operator": transaction_obj.operator.code if transaction_obj.operator else "",
            "amount": str(transaction_obj.amount),
            "charge": str(transaction_obj.charge),
            "total_debit": str(transaction_obj.total_debit),
            "customer_mobile": transaction_obj.customer_mobile,
            "description": transaction_obj.description,
            "payload": transaction_obj.request_payload,
        }

    @staticmethod
    def _sandbox_response(transaction_obj):
        provider = transaction_obj.provider
        configured_status = normalize_provider_status(provider_config(provider, "sandbox_status", ""), default="")
        default_status = "pending" if provider and provider.provider_type == "payout" else "success"
        status = configured_status or default_status
        provider_reference = ProviderExecutionService._provider_reference(provider)
        return {
            "status": status,
            "provider_reference": provider_reference,
            "message": f"{provider.name if provider else 'Provider'} accepted the request in sandbox mode.",
            "mode": "sandbox",
        }

    @staticmethod
    def _request_json(method, url, payload, headers=None, timeout=30):
        body = json.dumps(payload).encode("utf-8")
        request = Request(url, data=body, headers={"Content-Type": "application/json", **(headers or {})}, method=method)
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            raw = exc.read().decode("utf-8") if exc.fp else ""
            message = raw or str(exc)
            raise ValidationError({"code": "PROVIDER_REQUEST_FAILED", "message": message[:240]}) from exc
        except URLError as exc:
            raise ValidationError({"code": "PROVIDER_UNREACHABLE", "message": str(exc.reason)[:240]}) from exc

        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"raw_response": raw}

    @staticmethod
    def _live_response(transaction_obj):
        provider = transaction_obj.provider
        execute_path = provider_config(provider, "execute_path", "")
        if not provider or not provider.base_url or not execute_path:
            raise ValidationError(
                {
                    "code": "PROVIDER_CONFIG_REQUIRED",
                    "message": f"{provider.name if provider else 'Provider'} is missing live execution configuration.",
                }
            )

        url = urljoin(f"{provider.base_url.rstrip('/')}/", execute_path.lstrip("/"))
        headers = provider_config(provider, "headers", {}) or {}
        api_key = provider_config(provider, "api_key", "")
        if api_key and "Authorization" not in headers:
            headers["Authorization"] = f"Bearer {api_key}"
        timeout = int(provider_config(provider, "timeout_seconds", 30))
        response = ProviderExecutionService._request_json(
            "POST",
            url,
            ProviderExecutionService._build_transaction_payload(transaction_obj),
            headers=headers,
            timeout=timeout,
        )
        provider_reference = (
            response.get("provider_reference")
            or response.get("reference")
            or response.get("transaction_id")
            or response.get("id")
            or response.get("tid")
            or ProviderExecutionService._provider_reference(provider)
        )
        status = normalize_provider_status(
            response.get("status") or response.get("txStatus") or response.get("state") or response.get("payment_status"),
            default="pending",
        )
        return {
            "status": status,
            "provider_reference": provider_reference,
            "message": response.get("message") or response.get("description") or "Provider request processed.",
            "mode": "live",
            "provider_response": response,
        }

    @staticmethod
    def execute(transaction_obj):
        if provider_sandbox_enabled():
            return ProviderExecutionService._sandbox_response(transaction_obj)
        return ProviderExecutionService._live_response(transaction_obj)


class PaymentGatewayService:
    @staticmethod
    def gateway_provider():
        provider = Provider.objects.filter(provider_type="payment_gateway", active=True, health_status="healthy").first()
        if not provider:
            raise ValidationError({"code": "PAYMENT_GATEWAY_UNAVAILABLE", "message": "No healthy payment gateway is configured."})
        return provider

    @staticmethod
    def _serialize_order_payload(order, provider, payment_link="", payment_link_id="", mode="sandbox"):
        return {
            **(order.payload or {}),
            "provider_code": provider.code,
            "provider_name": provider.name,
            "payment_link": payment_link,
            "payment_link_id": payment_link_id,
            "mode": mode,
        }

    @staticmethod
    def _create_sandbox_order(order, provider):
        payment_link_id = f"PG-{uuid4().hex[:12].upper()}"
        payment_link = f"https://payments.quickzaps.local/pay/{order.reference}"
        order.provider_reference = payment_link_id
        order.payload = PaymentGatewayService._serialize_order_payload(order, provider, payment_link, payment_link_id, mode="sandbox")
        order.save(update_fields=["provider_reference", "payload", "updated_at"])
        return order

    @staticmethod
    def _create_live_order(order, provider):
        create_path = provider_config(provider, "create_order_path", "")
        if not provider.base_url or not create_path:
            raise ValidationError({"code": "PAYMENT_GATEWAY_CONFIG_REQUIRED", "message": f"{provider.name} is missing live order configuration."})
        url = urljoin(f"{provider.base_url.rstrip('/')}/", create_path.lstrip("/"))
        headers = provider_config(provider, "headers", {}) or {}
        api_key = provider_config(provider, "api_key", "")
        if api_key and "Authorization" not in headers:
            headers["Authorization"] = f"Bearer {api_key}"
        timeout = int(provider_config(provider, "timeout_seconds", 30))
        response = ProviderExecutionService._request_json(
            "POST",
            url,
            {"reference": order.reference, "amount": str(order.amount), "user_id": order.user_id},
            headers=headers,
            timeout=timeout,
        )
        payment_link = response.get("payment_link") or response.get("short_url") or response.get("checkout_url") or ""
        payment_link_id = response.get("payment_link_id") or response.get("id") or ProviderExecutionService._provider_reference(provider, prefix="PG")
        order.provider_reference = payment_link_id
        order.payload = PaymentGatewayService._serialize_order_payload(order, provider, payment_link, payment_link_id, mode="live")
        order.save(update_fields=["provider_reference", "payload", "updated_at"])
        return order

    @staticmethod
    @transaction.atomic
    def create_order(user, amount, payload=None, reference=""):
        amount = money(amount)
        if amount <= 0:
            raise ValidationError({"amount": "Amount must be greater than zero."})
        provider = PaymentGatewayService.gateway_provider()
        order, _ = PaymentGatewayOrder.objects.get_or_create(
            reference=reference or new_reference("PG"),
            defaults={"user": user, "amount": amount, "payload": payload or {}},
        )
        if provider_sandbox_enabled():
            return PaymentGatewayService._create_sandbox_order(order, provider)
        return PaymentGatewayService._create_live_order(order, provider)

    @staticmethod
    @transaction.atomic
    def complete_order(order, status="success", payload=None):
        if order.status != "created":
            return order
        payload = payload or {}
        normalized = normalize_provider_status(status, default="success")
        if normalized == "pending":
            return order
        order.status = "success" if normalized == "success" else "failed"
        if not order.provider_reference:
            order.provider_reference = payload.get("provider_reference") or f"PG-{order.reference}"
        order.payload = {**(order.payload or {}), **payload}
        order.save(update_fields=["status", "provider_reference", "payload", "updated_at"])
        if order.status == "success":
            WalletLedgerService.credit(order.user, order.amount, reference=order.reference, remarks="Payment gateway wallet credit")
        return order


class TransactionQuoteService:
    @staticmethod
    def quote(user, service, operator, amount):
        amount = money(amount)
        if user.status != "active" or not user.is_active:
            raise ValidationError({"code": "USER_INACTIVE", "message": "User is inactive or blocked."})
        if service.requires_kyc and user.kyc_status != "approved":
            raise ValidationError({"code": "KYC_REQUIRED", "message": "KYC approval is required for this service."})
        if not service.active:
            raise ValidationError({"code": "SERVICE_DISABLED", "message": "Service is not enabled."})
        if amount < service.min_amount or amount > service.max_amount:
            raise ValidationError({"amount": f"Amount must be between {service.min_amount} and {service.max_amount}."})
        provider = ProviderRouter.provider_for(service)
        pricing = CommissionCalculator.quote(user, service, operator, amount, provider)
        return {"service": service, "operator": operator, "amount": amount, "provider": provider, **pricing}


class CommissionPostingService:
    @staticmethod
    @transaction.atomic
    def post_success(transaction_obj):
        if transaction_obj.commission <= 0:
            return None
        existing = CommissionLedger.objects.filter(transaction=transaction_obj, entry_type="commission").first()
        if existing:
            return existing
        WalletLedgerService.credit(
            transaction_obj.initiated_by,
            transaction_obj.commission,
            entry_type="commission",
            transaction_obj=transaction_obj,
            reference=transaction_obj.reference,
            remarks=f"Commission for {transaction_obj.service.name}",
        )
        return CommissionLedger.objects.create(
            user=transaction_obj.initiated_by,
            transaction=transaction_obj,
            amount=transaction_obj.commission,
            entry_type="commission",
            remarks=f"Commission for {transaction_obj.reference}",
        )

    @staticmethod
    @transaction.atomic
    def reverse(transaction_obj):
        existing = CommissionLedger.objects.filter(transaction=transaction_obj, entry_type="commission").first()
        reversed_entry = CommissionLedger.objects.filter(transaction=transaction_obj, entry_type="commission_reversal").first()
        if not existing or reversed_entry:
            return None
        WalletLedgerService.debit(
            transaction_obj.initiated_by,
            existing.amount,
            entry_type="commission_reversal",
            transaction_obj=transaction_obj,
            reference=transaction_obj.reference,
            remarks=f"Commission reversal for {transaction_obj.service.name}",
        )
        return CommissionLedger.objects.create(
            user=transaction_obj.initiated_by,
            transaction=transaction_obj,
            amount=-existing.amount,
            entry_type="commission_reversal",
            remarks=f"Commission reversal for {transaction_obj.reference}",
        )


class TransactionExecutionService:
    @staticmethod
    @transaction.atomic
    def execute(user, service, operator, amount, customer_mobile, tpin="", idempotency_key="", payload=None, skip_tpin=False):
        payload = payload or {}
        if idempotency_key:
            existing = ServiceTransaction.objects.filter(initiated_by=user, idempotency_key=idempotency_key).first()
            if existing:
                return existing

        policy, _ = UserSecurityPolicy.objects.get_or_create(user=user)
        if not skip_tpin and (service.tpin_required or policy.transaction_tpin_required):
            if not user.tpin_hash or not check_password(tpin, user.tpin_hash):
                raise ValidationError({"code": "TPIN_INVALID", "message": "Transaction PIN is invalid."})

        quoted = TransactionQuoteService.quote(user, service, operator, amount)
        reference = new_reference("QZ")
        transaction_obj = ServiceTransaction.objects.create(
            reference=reference,
            initiated_by=user,
            service=service,
            operator=operator,
            provider=quoted["provider"],
            customer_mobile=customer_mobile,
            amount=quoted["amount"],
            charge=quoted["charge"],
            commission=quoted["commission"],
            admin_margin=quoted["admin_margin"],
            total_debit=quoted["total_debit"],
            idempotency_key=idempotency_key,
            status="pending",
            request_payload=payload,
            description=payload.get("description", ""),
        )
        WalletLedgerService.place_hold(user, quoted["total_debit"], transaction_obj, reference=reference)
        response = ProviderExecutionService.execute(transaction_obj)
        TransactionStatusService.apply_provider_status(transaction_obj, response["status"], response)
        return ServiceTransaction.objects.get(id=transaction_obj.id)


class TransactionStatusService:
    @staticmethod
    @transaction.atomic
    def apply_provider_status(transaction_obj, status, response=None):
        transaction_obj = ServiceTransaction.objects.select_for_update().get(id=transaction_obj.id)
        if transaction_obj.status in {"success", "failed", "refunded", "reversed"}:
            return transaction_obj
        response = response or {}
        transaction_obj.provider_status = status
        transaction_obj.provider_reference = response.get("provider_reference", transaction_obj.provider_reference)
        transaction_obj.response_payload = response
        if status == "success":
            WalletLedgerService.capture_hold(
                transaction_obj.initiated_by,
                transaction_obj.total_debit,
                transaction_obj,
                reference=transaction_obj.reference,
            )
            transaction_obj.status = "success"
            transaction_obj.save(update_fields=["status", "provider_status", "provider_reference", "response_payload", "updated_at"])
            CommissionPostingService.post_success(transaction_obj)
        elif status == "failed":
            WalletLedgerService.release_hold(
                transaction_obj.initiated_by,
                transaction_obj.total_debit,
                transaction_obj,
                reference=transaction_obj.reference,
            )
            transaction_obj.status = "failed"
            transaction_obj.save(update_fields=["status", "provider_status", "provider_reference", "response_payload", "updated_at"])
        else:
            transaction_obj.status = "pending"
            transaction_obj.save(update_fields=["status", "provider_status", "provider_reference", "response_payload", "updated_at"])
        return transaction_obj


class RefundService:
    @staticmethod
    @transaction.atomic
    def reverse_success(actor, transaction_obj, reason="", request=None):
        if transaction_obj.status != "success":
            raise ValidationError("Only successful transactions can be reversed.")
        CommissionPostingService.reverse(transaction_obj)
        WalletLedgerService.credit(
            transaction_obj.initiated_by,
            transaction_obj.total_debit,
            entry_type="refund",
            transaction_obj=transaction_obj,
            reference=transaction_obj.reference,
            remarks=reason or "Provider reversal",
            actor=actor,
        )
        transaction_obj.status = "reversed"
        transaction_obj.save(update_fields=["status", "updated_at"])
        AuditService.log(actor, "transaction.reverse", transaction_obj, request=request, metadata={"reason": reason})
        return transaction_obj


class WebhookProcessor:
    @staticmethod
    @transaction.atomic
    def process(provider, event_id, payload):
        event, created = ProviderWebhookEvent.objects.get_or_create(
            provider=provider,
            event_id=event_id,
            defaults={
                "transaction_reference": payload.get("reference", ""),
                "payload": payload,
            },
        )
        if not created and event.processed_at:
            return event
        reference = payload.get("reference")
        status = payload.get("status")
        if not reference or status not in {"success", "failed", "pending"}:
            event.processing_status = "ignored"
            event.processed_at = timezone.now()
            event.save(update_fields=["processing_status", "processed_at", "updated_at"])
            return event
        transaction_obj = ServiceTransaction.objects.get(reference=reference, provider=provider)
        TransactionStatusService.apply_provider_status(transaction_obj, status, payload)
        event.transaction_reference = reference
        event.processing_status = "processed"
        event.processed_at = timezone.now()
        event.save(update_fields=["transaction_reference", "processing_status", "processed_at", "updated_at"])
        return event


class NotificationDispatchService:
    @staticmethod
    @transaction.atomic
    def send_bulk(actor, message, request=None):
        qs = User.objects.filter(status="active")
        if message.target_role:
            qs = qs.filter(role=message.target_role)
        message.recipient_count = qs.count()
        message.status = "sent"
        message.sent_by = actor
        message.sent_at = timezone.now()
        message.save(update_fields=["recipient_count", "status", "sent_by", "sent_at", "updated_at"])
        if message.channel == "notification":
            notifications = [
                Notification(user=user, title=message.subject or "QuickZaps notification", body=message.body, sent_by=actor)
                for user in qs
            ]
            Notification.objects.bulk_create(notifications)
        AuditService.log(actor, "bulk_message.send", message, request=request, after={"recipient_count": message.recipient_count})
        return message
