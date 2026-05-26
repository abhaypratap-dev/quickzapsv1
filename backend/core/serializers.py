import re
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from rest_framework import serializers

from .models import (
    AepsMerchantProfile,
    AdminAPIMargin,
    AuditLog,
    BulkMessage,
    CommissionLedger,
    CommissionRule,
    EmailSetting,
    FundRequest,
    KYCProfile,
    LoginHistory,
    NewsItem,
    Notification,
    OnboardingApplication,
    Operator,
    PartnerAPISetting,
    PaymentGatewayOrder,
    PopupBanner,
    Provider,
    ProviderWebhookEvent,
    Role,
    Scheme,
    Service,
    ServicePackage,
    ServicePackageSlab,
    ServiceTransaction,
    UserSecurityPolicy,
    Wallet,
    WalletLedgerEntry,
)
from .services import CommissionCalculator


User = get_user_model()


class RoleSerializer(serializers.ModelSerializer):
    child_role_codes = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = [
            "id",
            "code",
            "name",
            "level",
            "can_create_downline",
            "can_transact",
            "can_earn_commission",
            "permissions",
            "child_roles",
            "child_role_codes",
            "active",
        ]

    def get_child_role_codes(self, obj):
        return list(obj.child_roles.values_list("code", flat=True))


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = "__all__"


class OperatorSerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(source="service.name", read_only=True)

    class Meta:
        model = Operator
        fields = "__all__"


class ServicePackageSlabSerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(source="service.name", read_only=True)

    class Meta:
        model = ServicePackageSlab
        fields = ["id", "service", "service_name", "service_amount", "created_at", "updated_at"]


class ServicePackageSerializer(serializers.ModelSerializer):
    slabs = ServicePackageSlabSerializer(many=True, read_only=True)

    class Meta:
        model = ServicePackage
        fields = ["id", "name", "description", "active", "slabs", "created_at", "updated_at"]


class SchemeSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source="role.name", read_only=True)
    role_code = serializers.CharField(source="role.code", read_only=True)

    class Meta:
        model = Scheme
        fields = "__all__"


class WalletSerializer(serializers.ModelSerializer):
    user_mobile = serializers.CharField(source="user.mobile", read_only=True)
    user_name = serializers.CharField(source="user.get_full_name", read_only=True)
    total_balance = serializers.DecimalField(max_digits=18, decimal_places=4, read_only=True)

    class Meta:
        model = Wallet
        fields = [
            "id",
            "user",
            "user_mobile",
            "user_name",
            "available_balance",
            "hold_balance",
            "cap_balance",
            "total_balance",
            "created_at",
            "updated_at",
        ]


class UserSecurityPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSecurityPolicy
        exclude = ["created_at", "updated_at"]


class PartnerAPISettingSerializer(serializers.ModelSerializer):
    user_mobile = serializers.CharField(source="user.mobile", read_only=True)
    user_name = serializers.CharField(source="user.get_full_name", read_only=True)
    dummy_mode = serializers.SerializerMethodField()
    api_key_editable = serializers.SerializerMethodField()

    class Meta:
        model = PartnerAPISetting
        fields = [
            "id",
            "user",
            "user_mobile",
            "user_name",
            "api_key",
            "allowed_ip",
            "allowed_ip2",
            "webhook_url",
            "active",
            "dummy_mode",
            "api_key_editable",
            "generated_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["user", "api_key", "generated_at", "created_at", "updated_at"]

    def get_dummy_mode(self, obj):
        from django.conf import settings

        return bool(getattr(settings, "PARTNER_API_DUMMY_MODE", False))

    def get_api_key_editable(self, obj):
        from django.conf import settings

        return not bool(getattr(settings, "PARTNER_API_DUMMY_MODE", False))


class PartnerAPISettingUpdateSerializer(serializers.ModelSerializer):
    api_key = serializers.CharField(required=False, allow_blank=False, trim_whitespace=True, max_length=128)

    class Meta:
        model = PartnerAPISetting
        fields = ["api_key", "allowed_ip", "allowed_ip2", "webhook_url", "active"]

    def validate_api_key(self, value):
        api_key = value.strip()
        if not api_key:
            raise serializers.ValidationError("API key cannot be blank.")
        queryset = PartnerAPISetting.objects.filter(api_key=api_key)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("This API key is already in use.")
        return api_key

    def update(self, instance, validated_data):
        api_key = validated_data.get("api_key")
        if api_key and api_key != instance.api_key:
            validated_data["generated_at"] = timezone.now()
        return super().update(instance, validated_data)


class UserSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source="role.name", read_only=True)
    role_code = serializers.CharField(source="role.code", read_only=True)
    parent_name = serializers.CharField(source="parent.get_full_name", read_only=True)
    parent_mobile = serializers.CharField(source="parent.mobile", read_only=True)
    scheme_name = serializers.CharField(source="scheme.name", read_only=True)
    service_package_name = serializers.CharField(source="service_package.name", read_only=True)
    wallet = WalletSerializer(read_only=True)
    security_policy = UserSecurityPolicySerializer(read_only=True)
    partner_api_setting = PartnerAPISettingSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "mobile",
            "email",
            "first_name",
            "last_name",
            "role",
            "role_name",
            "role_code",
            "parent",
            "parent_name",
            "parent_mobile",
            "status",
            "kyc_status",
            "scheme",
            "scheme_name",
            "service_package",
            "service_package_name",
            "cap_balance",
            "company_name",
            "business_type",
            "address",
            "city",
            "state",
            "pin_code",
            "dob",
            "pan_number",
            "aadhaar_number",
            "wallet",
            "security_policy",
            "partner_api_setting",
            "last_login",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["username", "created_at", "updated_at", "last_login"]


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    mpin = serializers.CharField(write_only=True, required=False, allow_blank=True)
    tpin = serializers.CharField(write_only=True, required=False, allow_blank=True)
    login_sms_otp_enabled = serializers.BooleanField(required=False, default=False)
    login_email_otp_enabled = serializers.BooleanField(required=False, default=False)
    login_whatsapp_otp_enabled = serializers.BooleanField(required=False, default=False)
    login_mpin_enabled = serializers.BooleanField(required=False, default=False)
    transaction_tpin_required = serializers.BooleanField(required=False, default=True)
    aadhaar_kyc_required = serializers.BooleanField(required=False, default=True)
    pan_kyc_required = serializers.BooleanField(required=False, default=True)
    cap_balance_enforced = serializers.BooleanField(required=False, default=False)

    class Meta:
        model = User
        fields = [
            "mobile",
            "email",
            "first_name",
            "last_name",
            "password",
            "mpin",
            "tpin",
            "role",
            "parent",
            "status",
            "scheme",
            "service_package",
            "cap_balance",
            "company_name",
            "business_type",
            "address",
            "city",
            "state",
            "pin_code",
            "dob",
            "pan_number",
            "aadhaar_number",
            "login_sms_otp_enabled",
            "login_email_otp_enabled",
            "login_whatsapp_otp_enabled",
            "login_mpin_enabled",
            "transaction_tpin_required",
            "aadhaar_kyc_required",
            "pan_kyc_required",
            "cap_balance_enforced",
        ]


class KYCProfileSerializer(serializers.ModelSerializer):
    user_mobile = serializers.CharField(source="user.mobile", read_only=True)
    user_name = serializers.CharField(source="user.get_full_name", read_only=True)
    role_name = serializers.CharField(source="user.role.name", read_only=True)

    class Meta:
        model = KYCProfile
        fields = "__all__"
        read_only_fields = ["reviewer", "reviewed_at", "created_at", "updated_at"]


class AepsMerchantProfileSerializer(serializers.ModelSerializer):
    user_mobile = serializers.CharField(source="user.mobile", read_only=True)
    user_name = serializers.CharField(source="user.get_full_name", read_only=True)
    can_access_services = serializers.BooleanField(read_only=True)
    next_step = serializers.CharField(read_only=True)

    class Meta:
        model = AepsMerchantProfile
        fields = [
            "id",
            "user",
            "user_mobile",
            "user_name",
            "merchant_login_id",
            "merchant_phone_number",
            "super_merchant_id",
            "fingpay_merchant_status",
            "status",
            "kyc_status",
            "can_access_services",
            "next_step",
            "device_imei",
            "latitude",
            "longitude",
            "merchant_state",
            "merchant_city_name",
            "merchant_district_name",
            "merchant_pin_code",
            "company_legal_name",
            "company_type",
            "company_bank_name",
            "bank_ifsc_code",
            "settlement_account_last4",
            "bank_account_name",
            "primary_key_id",
            "encode_fp_txn_id",
            "last_provider_message",
            "rejection_reason",
            "last_onboarded_at",
            "last_ekyc_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class AepsMerchantOnboardingSerializer(serializers.Serializer):
    merchant_login_id = serializers.RegexField(r"^[A-Za-z0-9]{4,80}$")
    merchant_pin = serializers.RegexField(r"^\d{4,12}$", write_only=True)
    first_name = serializers.CharField(max_length=40, trim_whitespace=True)
    last_name = serializers.CharField(max_length=40, trim_whitespace=True)
    middle_name = serializers.CharField(max_length=40, required=False, allow_blank=True)
    merchant_phone_number = serializers.RegexField(r"^[6-9]\d{9}$")
    merchant_address1 = serializers.CharField(max_length=120)
    merchant_address2 = serializers.CharField(max_length=120)
    merchant_state = serializers.IntegerField(min_value=1)
    merchant_city_name = serializers.CharField(max_length=80)
    merchant_district_name = serializers.CharField(max_length=80)
    merchant_pin_code = serializers.RegexField(r"^\d{6}$")
    company_legal_name = serializers.CharField(max_length=160)
    company_type = serializers.IntegerField(min_value=1)
    email_id = serializers.EmailField(required=False, allow_blank=True)
    aadhaar_number = serializers.RegexField(r"^\d{12}$", required=False, allow_blank=True, write_only=True)
    pan_number = serializers.CharField(max_length=20, required=False, allow_blank=True, trim_whitespace=True)
    gstin_number = serializers.CharField(max_length=30, required=False, allow_blank=True, trim_whitespace=True)
    company_or_shop_pan = serializers.CharField(max_length=20, required=False, allow_blank=True, trim_whitespace=True)
    bank_account_number = serializers.RegexField(r"^\d{6,40}$", write_only=True)
    bank_ifsc_code = serializers.RegexField(r"^[A-Z]{4}0[A-Z0-9]{6}$")
    company_bank_name = serializers.CharField(max_length=120)
    bank_account_name = serializers.CharField(max_length=160)
    device_imei = serializers.CharField(max_length=80, required=False, allow_blank=True)
    latitude = serializers.DecimalField(max_digits=10, decimal_places=7, required=False)
    longitude = serializers.DecimalField(max_digits=10, decimal_places=7, required=False)
    shop_address = serializers.CharField(max_length=160, required=False, allow_blank=True)
    shop_city = serializers.CharField(max_length=80, required=False, allow_blank=True)
    shop_district = serializers.CharField(max_length=80, required=False, allow_blank=True)
    shop_state = serializers.IntegerField(min_value=1, required=False)
    shop_pin_code = serializers.RegexField(r"^\d{6}$", required=False, allow_blank=True)
    merchant_pan_image_base64 = serializers.CharField(required=False, allow_blank=True, write_only=True)
    masked_aadhaar_image_base64 = serializers.CharField(required=False, allow_blank=True, write_only=True)
    background_image_of_shop_base64 = serializers.CharField(required=False, allow_blank=True, write_only=True)

    def validate_first_name(self, value):
        if not re.fullmatch(r"[A-Za-z0-9]+", value):
            raise serializers.ValidationError("Use letters and numbers only.")
        return value

    def validate_last_name(self, value):
        if not re.fullmatch(r"[A-Za-z0-9]+", value):
            raise serializers.ValidationError("Use letters and numbers only.")
        return value

    def validate_pan_number(self, value):
        value = (value or "").strip().upper()
        if value and not re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", value):
            raise serializers.ValidationError("Enter a valid PAN.")
        return value

    def validate_company_or_shop_pan(self, value):
        value = (value or "").strip().upper()
        if value and not re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", value):
            raise serializers.ValidationError("Enter a valid PAN.")
        return value

    def validate_bank_ifsc_code(self, value):
        return value.strip().upper()


class AepsKycOtpSerializer(serializers.Serializer):
    aadhaar_number = serializers.RegexField(r"^\d{12}$", required=False, allow_blank=True, write_only=True)
    pan_number = serializers.CharField(max_length=20, required=False, allow_blank=True, trim_whitespace=True)
    mobile_number = serializers.RegexField(r"^[6-9]\d{9}$", required=False, allow_blank=True)
    matm_serial_number = serializers.CharField(max_length=80, required=False, allow_blank=True)
    device_imei = serializers.CharField(max_length=80, required=False, allow_blank=True)
    latitude = serializers.DecimalField(max_digits=10, decimal_places=7, required=False)
    longitude = serializers.DecimalField(max_digits=10, decimal_places=7, required=False)


class AepsKycOtpValidateSerializer(serializers.Serializer):
    otp = serializers.RegexField(r"^\d{4,8}$", write_only=True)
    primary_key_id = serializers.IntegerField(required=False)
    encode_fp_txn_id = serializers.CharField(max_length=160, required=False, allow_blank=True)
    device_imei = serializers.CharField(max_length=80, required=False, allow_blank=True)


class AepsBiometricKycSerializer(serializers.Serializer):
    aadhaar_number = serializers.RegexField(r"^\d{12}$", required=False, allow_blank=True, write_only=True)
    bank_iin = serializers.CharField(max_length=20, required=False, allow_blank=True)
    indicator_for_uid = serializers.IntegerField(required=False, default=0, min_value=0, max_value=2)
    primary_key_id = serializers.IntegerField(required=False)
    encode_fp_txn_id = serializers.CharField(max_length=160, required=False, allow_blank=True)
    capture_response = serializers.JSONField(write_only=True)
    request_remarks = serializers.CharField(max_length=160, required=False, allow_blank=True)
    device_imei = serializers.CharField(max_length=80, required=False, allow_blank=True)


class AepsTransactionExecuteSerializer(serializers.Serializer):
    transaction_type = serializers.ChoiceField(choices=["CW", "BE", "MS", "M", "CD"])
    customer_mobile = serializers.RegexField(r"^[6-9]\d{9}$")
    aadhaar_number = serializers.RegexField(r"^\d{12}$", write_only=True)
    bank_iin = serializers.RegexField(r"^\d{6,12}$")
    amount = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("0.0000"), required=False, default=Decimal("0.0000"))
    merchant_pin = serializers.RegexField(r"^\d{4,12}$", write_only=True)
    merchant_transaction_id = serializers.RegexField(r"^[A-Za-z0-9_-]{6,40}$", required=False, allow_blank=True)
    indicator_for_uid = serializers.IntegerField(required=False, default=0, min_value=0, max_value=2)
    capture_response = serializers.JSONField(write_only=True)
    request_remarks = serializers.CharField(max_length=160, required=False, allow_blank=True)
    device_imei = serializers.CharField(max_length=80, required=False, allow_blank=True)
    device_transaction_id = serializers.CharField(max_length=80, required=False, allow_blank=True)
    language_code = serializers.CharField(max_length=8, required=False, default="en")
    latitude = serializers.DecimalField(max_digits=10, decimal_places=7, required=False)
    longitude = serializers.DecimalField(max_digits=10, decimal_places=7, required=False)

    def validate(self, attrs):
        transaction_type = attrs.get("transaction_type")
        amount = attrs.get("amount") or Decimal("0")
        if transaction_type in {"CW", "M", "CD"} and amount <= 0:
            raise serializers.ValidationError({"amount": "Amount is required for this AEPS transaction."})
        if transaction_type in {"BE", "MS"}:
            attrs["amount"] = Decimal("0.0000")
        return attrs


class OnboardingApplicationSerializer(serializers.ModelSerializer):
    requested_role_label = serializers.CharField(source="get_requested_role_display", read_only=True)
    submitted_by_name = serializers.CharField(source="submitted_by.get_full_name", read_only=True)
    agent_name = serializers.CharField(source="agent.get_full_name", read_only=True)
    parent_name = serializers.CharField(source="parent.get_full_name", read_only=True)
    parent_mobile = serializers.CharField(source="parent.mobile", read_only=True)
    parent_role_name = serializers.CharField(source="parent.role.name", read_only=True)
    approved_by_name = serializers.CharField(source="approved_by.get_full_name", read_only=True)
    created_user_mobile = serializers.CharField(source="created_user.mobile", read_only=True)

    class Meta:
        model = OnboardingApplication
        fields = "__all__"
        read_only_fields = [
            "status",
            "submitted_by",
            "agent",
            "parent_approved_by",
            "approved_by",
            "created_user",
            "pan_verification",
            "aadhaar_verification",
            "bank_verification",
            "gst_verification",
            "udyam_verification",
            "verification_mode",
            "rpd_reference_id",
            "rpd_link",
            "rpd_status",
            "review_note",
            "approved_at",
            "rejected_at",
            "created_at",
            "updated_at",
        ]

    def validate_requested_role(self, value):
        if value not in {"SDBR", "DBR", "RETAILER"}:
            raise serializers.ValidationError("Role must be SDBR, DBR, or RETAILER.")
        return value

    def validate(self, attrs):
        if self.instance is not None:
            return attrs
        required_files = ["live_photo", "shop_photo", "agent_photo", "business_photo"]
        missing_files = [field for field in required_files if not attrs.get(field)]
        if missing_files:
            raise serializers.ValidationError({field: "This photo is required for onboarding." for field in missing_files})
        for field in ["live_photo_geo", "shop_photo_geo", "agent_photo_geo"]:
            value = attrs.get(field) or {}
            if not isinstance(value, dict) or not value.get("captured_at"):
                raise serializers.ValidationError({field: "Geotagging is required for this photo."})
        if attrs.get("gst_number") and not attrs.get("gst_document"):
            raise serializers.ValidationError({"gst_document": "GST document is required when GST number is entered."})
        if attrs.get("udyam_number") and not attrs.get("udyam_document"):
            raise serializers.ValidationError({"udyam_document": "MSME/Udyam document is required when Udyam number is entered."})
        return attrs


class OnboardingReviewSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject"])
    note = serializers.CharField(required=False, allow_blank=True)


class WalletLedgerEntrySerializer(serializers.ModelSerializer):
    user_mobile = serializers.CharField(source="user.mobile", read_only=True)
    user_name = serializers.CharField(source="user.get_full_name", read_only=True)
    service_name = serializers.CharField(source="transaction.service.name", read_only=True)

    class Meta:
        model = WalletLedgerEntry
        fields = "__all__"


class FundRequestSerializer(serializers.ModelSerializer):
    user_mobile = serializers.CharField(source="user.mobile", read_only=True)
    user_name = serializers.CharField(source="user.get_full_name", read_only=True)
    reviewed_by_name = serializers.CharField(source="reviewed_by.get_full_name", read_only=True)

    class Meta:
        model = FundRequest
        fields = "__all__"
        read_only_fields = ["user", "status", "reviewed_by", "reviewed_at", "review_note", "created_at", "updated_at"]


class FundRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = FundRequest
        fields = ["amount", "method", "payment_reference", "note"]


class FundRequestReviewSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["approved", "rejected"])
    review_note = serializers.CharField(required=False, allow_blank=True)


class PaymentGatewayOrderSerializer(serializers.ModelSerializer):
    user_mobile = serializers.CharField(source="user.mobile", read_only=True)
    payment_link = serializers.SerializerMethodField()
    payment_link_id = serializers.SerializerMethodField()
    provider_name = serializers.SerializerMethodField()
    sandbox_mode = serializers.SerializerMethodField()

    class Meta:
        model = PaymentGatewayOrder
        fields = "__all__"
        read_only_fields = ["user", "reference", "status", "provider_reference", "payload", "created_at", "updated_at"]

    def get_payment_link(self, obj):
        return (obj.payload or {}).get("payment_link", "")

    def get_payment_link_id(self, obj):
        return (obj.payload or {}).get("payment_link_id", obj.provider_reference)

    def get_provider_name(self, obj):
        return (obj.payload or {}).get("provider_name", "")

    def get_sandbox_mode(self, obj):
        return (obj.payload or {}).get("mode") == "sandbox"


class CommissionRuleSerializer(serializers.ModelSerializer):
    scheme_name = serializers.CharField(source="scheme.name", read_only=True)
    service_name = serializers.CharField(source="service.name", read_only=True)
    operator_name = serializers.CharField(source="operator.name", read_only=True)

    class Meta:
        model = CommissionRule
        fields = "__all__"


class AdminAPIMarginSerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(source="service.name", read_only=True)
    operator_name = serializers.CharField(source="operator.name", read_only=True)
    provider_name = serializers.CharField(source="provider.name", read_only=True)

    class Meta:
        model = AdminAPIMargin
        fields = "__all__"


class CommissionLedgerSerializer(serializers.ModelSerializer):
    user_mobile = serializers.CharField(source="user.mobile", read_only=True)
    user_name = serializers.CharField(source="user.get_full_name", read_only=True)
    transaction_reference = serializers.CharField(source="transaction.reference", read_only=True)
    service_name = serializers.CharField(source="transaction.service.name", read_only=True)

    class Meta:
        model = CommissionLedger
        fields = "__all__"


class ProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Provider
        fields = "__all__"


class ServiceTransactionSerializer(serializers.ModelSerializer):
    user_mobile = serializers.CharField(source="initiated_by.mobile", read_only=True)
    user_name = serializers.CharField(source="initiated_by.get_full_name", read_only=True)
    service_name = serializers.CharField(source="service.name", read_only=True)
    operator_name = serializers.CharField(source="operator.name", read_only=True)
    provider_name = serializers.CharField(source="provider.name", read_only=True)

    class Meta:
        model = ServiceTransaction
        fields = "__all__"


class TransactionQuoteSerializer(serializers.Serializer):
    service = serializers.PrimaryKeyRelatedField(queryset=Service.objects.filter(active=True))
    operator = serializers.PrimaryKeyRelatedField(queryset=Operator.objects.filter(active=True), required=False, allow_null=True)
    amount = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("1.0000"))


class TransactionExecuteSerializer(TransactionQuoteSerializer):
    customer_mobile = serializers.CharField(max_length=20)
    tpin = serializers.CharField(write_only=True, required=False, allow_blank=True)
    idempotency_key = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)


class TransactionQuoteResultSerializer(serializers.Serializer):
    service = ServiceSerializer()
    operator = OperatorSerializer(allow_null=True)
    provider = ProviderSerializer()
    amount = serializers.DecimalField(max_digits=18, decimal_places=4)
    charge = serializers.DecimalField(max_digits=18, decimal_places=4)
    commission = serializers.DecimalField(max_digits=18, decimal_places=4)
    gross_commission = serializers.DecimalField(max_digits=18, decimal_places=4)
    tds = serializers.DecimalField(max_digits=18, decimal_places=4)
    surcharge = serializers.DecimalField(max_digits=18, decimal_places=4)
    gst = serializers.DecimalField(max_digits=18, decimal_places=4)
    admin_margin = serializers.DecimalField(max_digits=18, decimal_places=4)
    total_debit = serializers.DecimalField(max_digits=18, decimal_places=4)


class EmailSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailSetting
        fields = "__all__"


class NewsItemSerializer(serializers.ModelSerializer):
    target_role_name = serializers.CharField(source="target_role.name", read_only=True)

    class Meta:
        model = NewsItem
        fields = "__all__"


class PopupBannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = PopupBanner
        fields = "__all__"


class BulkMessageSerializer(serializers.ModelSerializer):
    target_role_name = serializers.CharField(source="target_role.name", read_only=True)
    sent_by_name = serializers.CharField(source="sent_by.get_full_name", read_only=True)

    class Meta:
        model = BulkMessage
        fields = "__all__"
        read_only_fields = ["status", "sent_by", "sent_at", "recipient_count", "created_at", "updated_at"]


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = "__all__"


class ProviderWebhookEventSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source="provider.name", read_only=True)

    class Meta:
        model = ProviderWebhookEvent
        fields = "__all__"


class LoginHistorySerializer(serializers.ModelSerializer):
    user_mobile = serializers.CharField(source="user.mobile", read_only=True)
    user_name = serializers.CharField(source="user.get_full_name", read_only=True)

    class Meta:
        model = LoginHistory
        fields = "__all__"


class AuditLogSerializer(serializers.ModelSerializer):
    actor_mobile = serializers.CharField(source="actor.mobile", read_only=True)
    actor_name = serializers.CharField(source="actor.get_full_name", read_only=True)

    class Meta:
        model = AuditLog
        fields = "__all__"


class WalletAdjustmentSerializer(serializers.Serializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    amount = serializers.DecimalField(max_digits=18, decimal_places=4)
    direction = serializers.ChoiceField(choices=["credit", "debit"])
    remarks = serializers.CharField(max_length=240)


class KYCReviewSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["approved", "rejected", "reupload_requested"])
    reason = serializers.CharField(required=False, allow_blank=True)


class RoleUpgradeSerializer(serializers.Serializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    new_role = serializers.PrimaryKeyRelatedField(queryset=Role.objects.filter(active=True))
    scheme = serializers.PrimaryKeyRelatedField(queryset=Scheme.objects.filter(active=True), required=False, allow_null=True)


class OTPPermissionUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSecurityPolicy
        exclude = ["created_at", "updated_at"]


class ServicePackageSlabWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServicePackageSlab
        fields = ["package", "service", "service_amount"]


class AdminDashboardSerializer(serializers.Serializer):
    totals = serializers.DictField()
    service_summary = serializers.ListField()
    trend = serializers.ListField()
    last_transactions = ServiceTransactionSerializer(many=True)
    wallet_totals = serializers.DictField()
    pending_counts = serializers.DictField()
    news = NewsItemSerializer(many=True)


def serialize_quote_for_response(quote):
    return {
        "service": ServiceSerializer(quote["service"]).data,
        "operator": OperatorSerializer(quote["operator"]).data if quote.get("operator") else None,
        "provider": ProviderSerializer(quote["provider"]).data,
        "amount": quote["amount"],
        "charge": quote["charge"],
        "commission": quote["commission"],
        "gross_commission": quote.get("gross_commission", quote["commission"]),
        "tds": quote.get("tds", Decimal("0")),
        "surcharge": quote.get("surcharge", Decimal("0")),
        "gst": quote.get("gst", Decimal("0")),
        "admin_margin": quote["admin_margin"],
        "total_debit": quote["total_debit"],
    }
