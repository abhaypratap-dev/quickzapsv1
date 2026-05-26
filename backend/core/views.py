from decimal import Decimal
import json
from datetime import timedelta
from types import SimpleNamespace
from secrets import token_urlsafe
from random import randint
from uuid import uuid4

from django.contrib.auth import authenticate
from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.utils.dateparse import parse_date
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
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
    User,
    UserSecurityPolicy,
    Wallet,
    WalletLedgerEntry,
)
from .serializers import (
    AepsBiometricKycSerializer,
    AepsKycOtpSerializer,
    AepsKycOtpValidateSerializer,
    AepsMerchantOnboardingSerializer,
    AepsMerchantProfileSerializer,
    AepsTransactionExecuteSerializer,
    AdminAPIMarginSerializer,
    AuditLogSerializer,
    BulkMessageSerializer,
    CommissionLedgerSerializer,
    CommissionRuleSerializer,
    EmailSettingSerializer,
    FundRequestCreateSerializer,
    FundRequestReviewSerializer,
    FundRequestSerializer,
    KYCProfileSerializer,
    KYCReviewSerializer,
    LoginHistorySerializer,
    NewsItemSerializer,
    NotificationSerializer,
    OTPPermissionUpdateSerializer,
    OnboardingApplicationSerializer,
    OnboardingReviewSerializer,
    OperatorSerializer,
    PartnerAPISettingSerializer,
    PartnerAPISettingUpdateSerializer,
    PaymentGatewayOrderSerializer,
    PopupBannerSerializer,
    ProviderSerializer,
    ProviderWebhookEventSerializer,
    RoleSerializer,
    RoleUpgradeSerializer,
    SchemeSerializer,
    ServicePackageSerializer,
    ServicePackageSlabSerializer,
    ServicePackageSlabWriteSerializer,
    ServiceSerializer,
    ServiceTransactionSerializer,
    TransactionExecuteSerializer,
    TransactionQuoteSerializer,
    UserCreateSerializer,
    UserSecurityPolicySerializer,
    UserSerializer,
    WalletAdjustmentSerializer,
    WalletLedgerEntrySerializer,
    WalletSerializer,
    serialize_quote_for_response,
)
from .fingpay_aeps import FingpayAepsClient, compact_provider_response
from .partner_api import (
    create_payment_link,
    execute_partner_transaction,
    find_operator,
    find_service,
    log_partner_request,
    partner_error,
    partner_success,
    settlement_payload,
    transaction_payload,
    validate_partner_request,
)
from .services import (
    AepsMerchantService,
    AuditService,
    FundRequestService,
    KYCReviewService,
    KYCSubmissionService,
    OnboardingService,
    NotificationDispatchService,
    PaymentGatewayService,
    RefundService,
    RoleUpgradeService,
    TransactionExecutionService,
    TransactionQuoteService,
    UserCreationService,
    WalletLedgerService,
    WebhookProcessor,
    assert_can_manage_user,
    get_client_ip,
    new_reference,
    scoped_user_queryset,
    user_has_permission,
)


def is_admin(user):
    return bool(user.is_authenticated and user.is_platform_admin)


def require_admin(user, permission=None):
    if is_admin(user):
        return
    if permission and user_has_permission(user, permission):
        return
    raise PermissionDenied("You do not have permission for this action.")


def validation_message(exc):
    detail = getattr(exc, "detail", exc)
    if isinstance(detail, dict):
        return "; ".join(f"{key}: {value}" for key, value in detail.items())
    if isinstance(detail, list):
        return "; ".join(str(item) for item in detail)
    return str(detail)


def paginate(viewset, queryset, serializer_class=None):
    page = viewset.paginate_queryset(queryset)
    serializer = (serializer_class or viewset.get_serializer_class())(page or queryset, many=True, context=viewset.get_serializer_context())
    if page is not None:
        return viewset.get_paginated_response(serializer.data)
    return Response(serializer.data)


def jwt_payload_for_user(user, request):
    refresh = RefreshToken.for_user(user)
    user.last_login = timezone.now()
    user.save(update_fields=["last_login"])
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "user": UserSerializer(user, context={"request": request}).data,
    }


def dummy_api_setting_payload(user):
    return {
        "id": 0,
        "user": user.id,
        "user_mobile": user.mobile,
        "user_name": user.get_full_name(),
        "api_key": getattr(settings, "PARTNER_API_DUMMY_KEY", "quickzaps-dummy-key"),
        "allowed_ip": None,
        "allowed_ip2": None,
        "webhook_url": "",
        "active": True,
        "dummy_mode": True,
        "api_key_editable": False,
        "generated_at": timezone.now(),
        "created_at": timezone.now(),
        "updated_at": timezone.now(),
    }


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get("username") or request.data.get("mobile") or request.data.get("user_id")
        password = request.data.get("password")
        user = authenticate(request, username=username, password=password)
        LoginHistory.objects.create(
            user=user if user else None,
            username=username or "",
            success=bool(user),
            ip_address=get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )
        if not user:
            return Response({"error": {"code": "AUTH_INVALID_CREDENTIALS", "message": "Login failed."}}, status=400)
        if user.status != "active" or not user.is_active:
            return Response({"error": {"code": "USER_INACTIVE", "message": "User is inactive or blocked."}}, status=403)
        return Response(jwt_payload_for_user(user, request))


class LegacyLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get("UserName") or request.data.get("username") or request.data.get("mobile")
        password = request.data.get("Password") or request.data.get("password")
        user = authenticate(request, username=username, password=password)
        LoginHistory.objects.create(
            user=user if user else None,
            username=username or "",
            success=bool(user),
            ip_address=get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )
        if not user:
            return Response({"status": "FAILED", "message": "Invalid login"}, status=400)
        if user.status != "active" or not user.is_active:
            return Response({"status": "FAILED", "message": "User is inactive or blocked"}, status=403)

        if user.is_platform_admin:
            otp = f"{randint(100000, 999999)}"
            otp_token = token_urlsafe(24)
            cache.set(f"legacy_admin_otp:{otp_token}", {"otp": otp, "user_id": user.id}, timeout=300)
            request.session["legacy_admin_otp"] = otp
            request.session["legacy_admin_user_id"] = user.id
            payload = {"status": "OTP_REQUIRED", "otpToken": otp_token}
            if settings.DEBUG:
                payload["devOtp"] = otp
            return Response(payload)

        response = {
            "status": "SUCCESS",
            "redirectUrl": "/User/UserDashboard/Dashboard",
            **jwt_payload_for_user(user, request),
        }
        return Response(response)


class LegacyVerifyOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        entered = str(request.data.get("enteredOtp") or request.data.get("otp") or request.data.get("OTP") or "")
        otp_token = request.data.get("otpToken") or request.data.get("token")
        cached = cache.get(f"legacy_admin_otp:{otp_token}") if otp_token else None
        session_otp = request.session.get("legacy_admin_otp")
        session_user_id = request.session.get("legacy_admin_user_id")

        otp = cached["otp"] if cached else session_otp
        user_id = cached["user_id"] if cached else session_user_id
        if not otp or entered != str(otp) or not user_id:
            return Response({"status": "FAILED"}, status=400)

        user = User.objects.get(id=user_id)
        request.session.pop("legacy_admin_otp", None)
        request.session.pop("legacy_admin_user_id", None)
        if otp_token:
            cache.delete(f"legacy_admin_otp:{otp_token}")
        return Response(
            {
                "status": "SUCCESS",
                "redirectUrl": "/Admin/AdminDashboard/Dashboard",
                **jwt_payload_for_user(user, request),
            }
        )


class MeView(APIView):
    def get(self, request):
        return Response(UserSerializer(request.user, context={"request": request}).data)


class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    search_fields = ["code", "name"]
    ordering_fields = ["level", "name"]

    def perform_create(self, serializer):
        require_admin(self.request.user)
        serializer.save()

    def perform_update(self, serializer):
        require_admin(self.request.user)
        serializer.save()


class UserViewSet(viewsets.ModelViewSet):
    serializer_class = UserSerializer
    search_fields = ["mobile", "email", "first_name", "last_name", "company_name"]
    ordering_fields = ["created_at", "mobile", "status"]
    filterset_fields = ["status", "role", "kyc_status", "parent", "scheme", "service_package"]

    def get_queryset(self):
        return scoped_user_queryset(self.request.user).select_related("role", "parent", "scheme", "service_package").prefetch_related("wallet")

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        return UserSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = UserCreationService.create_user(request.user, serializer.validated_data, request=request)
        return Response(UserSerializer(user, context={"request": request}).data, status=201)

    def perform_update(self, serializer):
        target = self.get_object()
        assert_can_manage_user(self.request.user, target)
        before = UserSerializer(target, context={"request": self.request}).data
        user = serializer.save()
        AuditService.log(self.request.user, "user.update", user, before=before, after=serializer.data, request=self.request)

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        assert_can_manage_user(request.user, user)
        user.soft_delete()
        AuditService.log(request.user, "user.delete", user, request=request)
        return Response(status=204)

    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        user = self.get_object()
        assert_can_manage_user(request.user, user)
        user.status = "active"
        user.is_active = True
        user.deleted_at = None
        user.save(update_fields=["status", "is_active", "deleted_at", "updated_at"])
        AuditService.log(request.user, "user.restore", user, request=request)
        return Response(UserSerializer(user, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="set-status")
    def set_status(self, request, pk=None):
        user = self.get_object()
        assert_can_manage_user(request.user, user)
        status_value = request.data.get("status")
        if status_value not in {"active", "inactive", "signup", "deleted"}:
            raise ValidationError({"status": "Invalid status."})
        user.status = status_value
        user.is_active = status_value == "active"
        if status_value == "deleted":
            user.deleted_at = timezone.now()
        user.save(update_fields=["status", "is_active", "deleted_at", "updated_at"])
        AuditService.log(request.user, "user.status.change", user, request=request, after={"status": status_value})
        return Response(UserSerializer(user, context={"request": request}).data)

    @action(detail=False, methods=["post"])
    def upgrade(self, request):
        serializer = RoleUpgradeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = RoleUpgradeService.upgrade(
            request.user,
            serializer.validated_data["user"],
            serializer.validated_data["new_role"],
            serializer.validated_data.get("scheme"),
            request=request,
        )
        return Response(UserSerializer(user, context={"request": request}).data)

    @action(detail=True, methods=["patch"], url_path="security-policy")
    def security_policy(self, request, pk=None):
        user = self.get_object()
        assert_can_manage_user(request.user, user)
        policy, _ = UserSecurityPolicy.objects.get_or_create(user=user)
        serializer = OTPPermissionUpdateSerializer(policy, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        AuditService.log(request.user, "security_policy.update", policy, request=request)
        return Response(UserSecurityPolicySerializer(policy).data)


class PartnerAPISettingViewSet(viewsets.ModelViewSet):
    serializer_class = PartnerAPISettingSerializer
    filterset_fields = ["active", "user"]
    search_fields = ["user__mobile", "user__email", "webhook_url", "api_key"]

    def get_queryset(self):
        if settings.PARTNER_API_DUMMY_MODE:
            return PartnerAPISetting.objects.none()
        return PartnerAPISetting.objects.select_related("user", "user__role").filter(user__in=scoped_user_queryset(self.request.user))

    def get_serializer_class(self):
        if self.action in {"update", "partial_update", "mine"} and self.request.method in {"PATCH", "PUT"}:
            return PartnerAPISettingUpdateSerializer
        return PartnerAPISettingSerializer

    def create(self, request, *args, **kwargs):
        require_admin(request.user)
        user_id = request.data.get("user")
        if not user_id:
            raise ValidationError({"user": "User is required."})
        user = User.objects.get(id=user_id)
        assert_can_manage_user(request.user, user)
        if settings.PARTNER_API_DUMMY_MODE:
            return Response(dummy_api_setting_payload(user), status=201)
        setting, _ = PartnerAPISetting.objects.get_or_create(user=user)
        serializer = PartnerAPISettingUpdateSerializer(setting, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        AuditService.log(request.user, "partner_api_setting.create", setting, request=request)
        return Response(PartnerAPISettingSerializer(setting).data, status=201)

    def perform_update(self, serializer):
        setting = self.get_object()
        assert_can_manage_user(self.request.user, setting.user)
        if not self.request.user.is_platform_admin and setting.user_id != self.request.user.id:
            raise PermissionDenied("You can only update your own API settings.")
        serializer.save()
        AuditService.log(self.request.user, "partner_api_setting.update", setting, request=self.request)

    @action(detail=False, methods=["get", "patch"], url_path="mine")
    def mine(self, request):
        if settings.PARTNER_API_DUMMY_MODE:
            return Response(dummy_api_setting_payload(request.user))
        setting, _ = PartnerAPISetting.objects.get_or_create(user=request.user)
        if request.method == "PATCH":
            serializer = PartnerAPISettingUpdateSerializer(setting, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            AuditService.log(request.user, "partner_api_setting.update.mine", setting, request=request)
        return Response(PartnerAPISettingSerializer(setting).data)

    @action(detail=False, methods=["post"], url_path="rotate")
    def rotate_mine(self, request):
        if settings.PARTNER_API_DUMMY_MODE:
            return Response(dummy_api_setting_payload(request.user))
        setting, _ = PartnerAPISetting.objects.get_or_create(user=request.user)
        setting.rotate_key()
        AuditService.log(request.user, "partner_api_setting.rotate.mine", setting, request=request)
        return Response(PartnerAPISettingSerializer(setting).data)

    @action(detail=True, methods=["post"], url_path="rotate")
    def rotate(self, request, pk=None):
        if settings.PARTNER_API_DUMMY_MODE:
            return Response(dummy_api_setting_payload(request.user))
        setting = self.get_object()
        assert_can_manage_user(request.user, setting.user)
        if not request.user.is_platform_admin and setting.user_id != request.user.id:
            raise PermissionDenied("You can only rotate your own API key.")
        setting.rotate_key()
        AuditService.log(request.user, "partner_api_setting.rotate", setting, request=request)
        return Response(PartnerAPISettingSerializer(setting).data)


class DeveloperAPISettingsView(APIView):
    def get(self, request):
        if settings.PARTNER_API_DUMMY_MODE:
            return Response(dummy_api_setting_payload(request.user))
        setting, _ = PartnerAPISetting.objects.get_or_create(user=request.user)
        return Response(PartnerAPISettingSerializer(setting).data)


class DeveloperAPIGenerateKeyView(APIView):
    def post(self, request):
        if settings.PARTNER_API_DUMMY_MODE:
            return Response({"status": "SUCCESS", "apiKey": settings.PARTNER_API_DUMMY_KEY, "data": dummy_api_setting_payload(request.user)})
        setting, _ = PartnerAPISetting.objects.get_or_create(user=request.user)
        setting.rotate_key()
        AuditService.log(request.user, "developer_api_key.rotate", setting, request=request)
        return Response({"status": "SUCCESS", "apiKey": setting.api_key, "data": PartnerAPISettingSerializer(setting).data})


class DeveloperAPISaveSettingsView(APIView):
    def post(self, request):
        if settings.PARTNER_API_DUMMY_MODE:
            payload = dummy_api_setting_payload(request.user)
            payload["allowed_ip"] = request.data.get("AllowedIp") or request.data.get("allowed_ip") or None
            payload["allowed_ip2"] = request.data.get("AllowedIP2") or request.data.get("allowed_ip2") or None
            payload["webhook_url"] = request.data.get("WebhookUrl") or request.data.get("webhook_url") or ""
            return Response({"status": "SUCCESS", "data": payload})
        setting, _ = PartnerAPISetting.objects.get_or_create(user=request.user)
        data = {
            "api_key": request.data.get("ApiKey") or request.data.get("api_key") or setting.api_key,
            "allowed_ip": request.data.get("AllowedIp") or request.data.get("allowed_ip") or None,
            "allowed_ip2": request.data.get("AllowedIP2") or request.data.get("allowed_ip2") or None,
            "webhook_url": request.data.get("WebhookUrl") or request.data.get("webhook_url") or "",
            "active": request.data.get("active", True),
        }
        serializer = PartnerAPISettingUpdateSerializer(setting, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        AuditService.log(request.user, "developer_api_setting.save", setting, request=request)
        return Response({"status": "SUCCESS", "data": PartnerAPISettingSerializer(setting).data})


class AepsViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def _profile_state(self, request):
        payload = AepsMerchantService.get_profile_payload(request.user)
        profile = payload.pop("profile")
        payload["profile"] = AepsMerchantProfileSerializer(profile, context={"request": request}).data if profile else None
        return payload

    @action(detail=False, methods=["get"])
    def profile(self, request):
        return Response(self._profile_state(request))

    @action(detail=False, methods=["post"])
    def onboard(self, request):
        serializer = AepsMerchantOnboardingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = AepsMerchantService.onboard(request.user, serializer.validated_data, request=request)
        payload = self._profile_state(request)
        payload["provider_response"] = profile.onboarding_response
        return Response(payload, status=201)

    @action(detail=False, methods=["post"], url_path="kyc/send-otp")
    def kyc_send_otp(self, request):
        serializer = AepsKycOtpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile, response = AepsMerchantService.send_ekyc_otp(request.user, serializer.validated_data, request=request)
        payload = self._profile_state(request)
        payload["provider_response"] = compact_provider_response(response)
        payload["profile"] = AepsMerchantProfileSerializer(profile, context={"request": request}).data
        return Response(payload)

    @action(detail=False, methods=["post"], url_path="kyc/validate-otp")
    def kyc_validate_otp(self, request):
        serializer = AepsKycOtpValidateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile, response = AepsMerchantService.validate_ekyc_otp(request.user, serializer.validated_data, request=request)
        payload = self._profile_state(request)
        payload["provider_response"] = compact_provider_response(response)
        payload["profile"] = AepsMerchantProfileSerializer(profile, context={"request": request}).data
        return Response(payload)

    @action(detail=False, methods=["post"], url_path="kyc/biometric")
    def kyc_biometric(self, request):
        serializer = AepsBiometricKycSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile, response = AepsMerchantService.biometric_ekyc(request.user, serializer.validated_data, request=request)
        payload = self._profile_state(request)
        payload["provider_response"] = compact_provider_response(response)
        payload["profile"] = AepsMerchantProfileSerializer(profile, context={"request": request}).data
        return Response(payload)

    @action(detail=False, methods=["post"], url_path="kyc/status")
    def kyc_status(self, request):
        profile, response = AepsMerchantService.refresh_ekyc_status(request.user, request=request)
        payload = self._profile_state(request)
        payload["provider_response"] = compact_provider_response(response)
        payload["profile"] = AepsMerchantProfileSerializer(profile, context={"request": request}).data
        return Response(payload)

    @action(detail=False, methods=["get"], url_path="banks")
    def banks(self, request):
        response = FingpayAepsClient().bank_details()
        return Response(compact_provider_response(response))

    @action(detail=False, methods=["post"], url_path="transactions/execute")
    def execute_transaction(self, request):
        serializer = AepsTransactionExecuteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        transaction_obj, provider_response = AepsMerchantService.execute_transaction(request.user, serializer.validated_data, request=request)
        return Response(
            {
                "transaction": ServiceTransactionSerializer(transaction_obj).data,
                "provider_response": provider_response,
                "profile": self._profile_state(request)["profile"],
            },
            status=201,
        )


class KYCProfileViewSet(viewsets.ModelViewSet):
    serializer_class = KYCProfileSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filterset_fields = ["status", "user__role"]
    search_fields = ["user__mobile", "user__email", "user__first_name", "user__last_name", "pan_number", "aadhaar_number"]

    def get_queryset(self):
        users = scoped_user_queryset(self.request.user)
        return KYCProfile.objects.select_related("user", "user__role", "reviewer").filter(user__in=users)

    @action(detail=False, methods=["get"])
    def mine(self, request):
        profile, _ = KYCProfile.objects.get_or_create(user=request.user)
        return Response(KYCProfileSerializer(profile, context={"request": request}).data)

    @action(detail=False, methods=["post"])
    def submit(self, request):
        profile = KYCSubmissionService.submit(request.user, request.data, request.FILES, request=request)
        return Response(KYCProfileSerializer(profile, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        serializer = KYCReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = KYCReviewService.review(
            request.user,
            self.get_object(),
            serializer.validated_data["status"],
            serializer.validated_data.get("reason", ""),
            request=request,
        )
        return Response(KYCProfileSerializer(profile, context={"request": request}).data)


class OnboardingApplicationViewSet(viewsets.ModelViewSet):
    serializer_class = OnboardingApplicationSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filterset_fields = ["status", "requested_role", "parent", "direct_to_admin"]
    search_fields = ["mobile", "email", "full_name", "business_name", "pan_number", "aadhaar_number"]
    ordering_fields = ["created_at", "updated_at", "status"]

    def get_queryset(self):
        queryset = OnboardingApplication.objects.select_related(
            "submitted_by",
            "agent",
            "parent",
            "parent__role",
            "parent_approved_by",
            "approved_by",
            "created_user",
        )
        if self.request.user.is_platform_admin:
            return queryset
        return queryset.filter(Q(submitted_by=self.request.user) | Q(agent=self.request.user) | Q(parent=self.request.user))

    def _normalized_data(self, request):
        data = request.data.copy()
        for field in ["live_photo_geo", "shop_photo_geo", "agent_photo_geo"]:
            value = data.get(field)
            if isinstance(value, str):
                try:
                    data[field] = json.loads(value) if value else {}
                except json.JSONDecodeError:
                    data[field] = {}
        return data

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=self._normalized_data(request))
        serializer.is_valid(raise_exception=True)
        application = serializer.save(submitted_by=request.user, agent=request.user)
        application = OnboardingService.prepare_application(application, request=request)
        return Response(self.get_serializer(application).data, status=201)

    def _verification_subject(self, data):
        dob = parse_date(str(data.get("dob") or ""))
        if not dob:
            raise ValidationError({"dob": "Enter DOB in YYYY-MM-DD format."})
        return SimpleNamespace(
            id=None,
            mobile=str(data.get("mobile") or ""),
            email=str(data.get("email") or ""),
            full_name=str(data.get("full_name") or ""),
            dob=dob,
            aadhaar_number=str(data.get("aadhaar_number") or ""),
            pan_number=str(data.get("pan_number") or ""),
            account_holder_name=str(data.get("account_holder_name") or data.get("full_name") or ""),
            account_number=str(data.get("account_number") or ""),
            ifsc=str(data.get("ifsc") or ""),
            bank_name=str(data.get("bank_name") or ""),
            upi_id=str(data.get("upi_id") or ""),
            business_name=str(data.get("business_name") or ""),
            gst_number=str(data.get("gst_number") or ""),
            udyam_number=str(data.get("udyam_number") or ""),
        )

    @action(detail=False, methods=["post"], url_path="verify-identity")
    def verify_identity(self, request):
        required = ["mobile", "email", "full_name", "dob", "pan_number"]
        missing = [field for field in required if not request.data.get(field)]
        if missing:
            raise ValidationError({field: "Required before identity verification." for field in missing})
        from . import cashfree

        subject = self._verification_subject(request.data)
        pan = cashfree.verify_pan(subject)
        pan_valid = str(pan.get("status", "")).upper() == "VALID"
        return Response({"verified": pan_valid, "mode": cashfree.mode_name(), "pan_verification": pan})

    @action(detail=False, methods=["post"], url_path="digilocker-init")
    def digilocker_init(self, request):
        from . import cashfree

        verification_id = f"DIGI-{uuid4().hex[:12]}"
        redirect_url = request.data.get("redirect_url") or ""
        result = cashfree.digilocker_create_url(verification_id, redirect_url=redirect_url or None)
        return Response(result)

    @action(detail=False, methods=["get"], url_path="digilocker-status")
    def digilocker_status(self, request):
        from . import cashfree

        verification_id = request.query_params.get("verification_id")
        if not verification_id:
            raise ValidationError({"verification_id": "Required."})
        result = cashfree.digilocker_get_status(verification_id)
        return Response(result)

    @action(detail=False, methods=["get"], url_path="digilocker-document")
    def digilocker_document(self, request):
        from . import cashfree

        verification_id = request.query_params.get("verification_id")
        if not verification_id:
            raise ValidationError({"verification_id": "Required."})
        result = cashfree.digilocker_get_document(verification_id, document_type="AADHAAR")
        aadhaar_ok = str(result.get("status", "")).upper() == "SUCCESS"
        return Response({"verified": aadhaar_ok, "mode": cashfree.mode_name(), "aadhaar_verification": result})

    @action(detail=False, methods=["post"], url_path="verify-bank")
    def verify_bank(self, request):
        required = ["mobile", "full_name", "dob", "account_holder_name", "account_number", "ifsc"]
        missing = [field for field in required if not request.data.get(field)]
        if missing:
            raise ValidationError({field: "Required before bank verification." for field in missing})
        from . import cashfree

        subject = self._verification_subject(request.data)
        bank = cashfree.create_reverse_penny_drop(subject)
        status_value = str(bank.get("rpd_status") or bank.get("status") or "").upper()
        verified = status_value in {"PAID", "VALID", "SUCCESS", "VERIFIED"}
        return Response({"verified": verified, "mode": cashfree.mode_name(), "bank_verification": bank})

    @action(detail=False, methods=["post"], url_path="verify-business")
    def verify_business(self, request):
        required = ["business_name", "business_address", "city", "state", "pin_code"]
        missing = [field for field in required if not request.data.get(field)]
        if missing:
            raise ValidationError({field: "Required before business verification." for field in missing})
        from . import cashfree

        subject = self._verification_subject({**request.data, "dob": request.data.get("dob") or "2000-01-01"})
        gst = cashfree.verify_gstin(subject)
        udyam = cashfree.verify_udyam(subject)
        gst_required = bool(subject.gst_number)
        udyam_required = bool(subject.udyam_number)
        gst_ok = not gst_required or str(gst.get("status", "")).upper() in {"VALID", "SUCCESS"} or str(gst.get("taxpayer_status", "")).upper() == "ACTIVE"
        udyam_ok = not udyam_required or str(udyam.get("status", "")).upper() in {"VALID", "SUCCESS", "PENDING_MANUAL_REVIEW"}
        return Response({"verified": gst_ok and udyam_ok, "mode": cashfree.mode_name(), "gst_verification": gst, "udyam_verification": udyam})

    @action(detail=False, methods=["get"])
    def parents(self, request):
        requested_role = request.query_params.get("requested_role") or request.query_params.get("role") or "RETAILER"
        parents = OnboardingService.eligible_parent_queryset(requested_role).order_by("role__level", "first_name", "mobile")
        data = [
            {
                "id": parent.id,
                "mobile": parent.mobile,
                "name": parent.get_full_name() or parent.mobile,
                "role_name": parent.role.name if parent.role else "",
                "role_code": parent.role.code if parent.role else "",
            }
            for parent in parents
        ]
        return Response(data)

    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        application = self.get_object()
        serializer = OnboardingReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        note = serializer.validated_data.get("note", "")
        if serializer.validated_data["action"] == "approve":
            application = OnboardingService.approve(request.user, application, note=note, request=request)
        else:
            application = OnboardingService.reject(request.user, application, note=note, request=request)
        return Response(self.get_serializer(application).data)


class WalletViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = WalletSerializer
    search_fields = ["user__mobile", "user__first_name", "user__last_name", "user__company_name"]

    def get_queryset(self):
        return Wallet.objects.select_related("user", "user__role").filter(user__in=scoped_user_queryset(self.request.user))

    @action(detail=False, methods=["get"])
    def mine(self, request):
        wallet, _ = Wallet.objects.get_or_create(user=request.user)
        return Response(WalletSerializer(wallet).data)

    @action(detail=False, methods=["get"])
    def ledger(self, request):
        qs = WalletLedgerEntry.objects.select_related("wallet", "user", "transaction", "transaction__service").filter(
            user__in=scoped_user_queryset(request.user)
        )
        user_id = request.query_params.get("user")
        if user_id:
            qs = qs.filter(user_id=user_id)
        return paginate(self, qs, WalletLedgerEntrySerializer)

    @action(detail=False, methods=["post"])
    def adjust(self, request):
        require_admin(request.user, "wallet.adjust.admin")
        serializer = WalletAdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target = serializer.validated_data["user"]
        amount = serializer.validated_data["amount"]
        remarks = serializer.validated_data["remarks"]
        if serializer.validated_data["direction"] == "credit":
            WalletLedgerService.credit(target, amount, entry_type="adjustment", reference=new_reference("ADJ"), remarks=remarks, actor=request.user)
        else:
            WalletLedgerService.debit(target, amount, entry_type="adjustment", reference=new_reference("ADJ"), remarks=remarks, actor=request.user)
        AuditService.log(request.user, "wallet.adjust", target.wallet, request=request, metadata=serializer.validated_data)
        return Response(WalletSerializer(target.wallet).data)


class FundRequestViewSet(viewsets.ModelViewSet):
    serializer_class = FundRequestSerializer
    filterset_fields = ["status", "method", "user"]
    search_fields = ["user__mobile", "payment_reference", "note"]

    def get_queryset(self):
        return FundRequest.objects.select_related("user", "reviewed_by").filter(user__in=scoped_user_queryset(self.request.user))

    def get_serializer_class(self):
        if self.action == "create":
            return FundRequestCreateSerializer
        return FundRequestSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        serializer = FundRequestReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        fund_request = FundRequestService.review(
            request.user,
            self.get_object(),
            serializer.validated_data["status"],
            serializer.validated_data.get("review_note", ""),
            request=request,
        )
        return Response(FundRequestSerializer(fund_request).data)


class PaymentGatewayOrderViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentGatewayOrderSerializer

    def get_queryset(self):
        return PaymentGatewayOrder.objects.select_related("user").filter(user__in=scoped_user_queryset(self.request.user))

    def create(self, request, *args, **kwargs):
        amount = Decimal(str(request.data.get("amount", "0")))
        order = PaymentGatewayService.create_order(request.user, amount, payload=request.data)
        return Response(PaymentGatewayOrderSerializer(order).data, status=201)

    def _complete_order(self, request, pk=None):
        order = self.get_object()
        order = PaymentGatewayService.complete_order(order, request.data.get("status", "success"), request.data)
        return Response(PaymentGatewayOrderSerializer(order).data)

    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        return self._complete_order(request, pk)

    @action(detail=True, methods=["post"], url_path="mock-callback")
    def mock_callback(self, request, pk=None):
        return self._complete_order(request, pk)


class ServiceViewSet(viewsets.ModelViewSet):
    queryset = Service.objects.all()
    serializer_class = ServiceSerializer
    filterset_fields = ["category", "active", "requires_kyc"]
    search_fields = ["code", "name"]


class OperatorViewSet(viewsets.ModelViewSet):
    queryset = Operator.objects.select_related("service").all()
    serializer_class = OperatorSerializer
    filterset_fields = ["service", "active"]
    search_fields = ["code", "name", "service__name"]


class ProviderViewSet(viewsets.ModelViewSet):
    queryset = Provider.objects.all()
    serializer_class = ProviderSerializer
    filterset_fields = ["provider_type", "active", "health_status"]
    search_fields = ["code", "name"]


class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ServiceTransactionSerializer
    filterset_fields = ["status", "service", "operator", "provider", "initiated_by"]
    search_fields = ["reference", "provider_reference", "customer_mobile", "initiated_by__mobile"]
    ordering_fields = ["created_at", "amount", "status"]

    def get_queryset(self):
        return ServiceTransaction.objects.select_related("initiated_by", "service", "operator", "provider").filter(
            initiated_by__in=scoped_user_queryset(self.request.user)
        )

    @action(detail=False, methods=["post"])
    def quote(self, request):
        serializer = TransactionQuoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        service = serializer.validated_data["service"]
        operator = serializer.validated_data.get("operator")
        if operator and operator.service_id != service.id:
            raise ValidationError({"operator": "Operator does not belong to the selected service."})
        quote = TransactionQuoteService.quote(request.user, service, operator, serializer.validated_data["amount"])
        return Response(serialize_quote_for_response(quote))

    @action(detail=False, methods=["post"])
    def execute(self, request):
        serializer = TransactionExecuteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        service = serializer.validated_data["service"]
        operator = serializer.validated_data.get("operator")
        if operator and operator.service_id != service.id:
            raise ValidationError({"operator": "Operator does not belong to the selected service."})
        payload = {
            "description": serializer.validated_data.get("description", ""),
        }
        tx = TransactionExecutionService.execute(
            request.user,
            service,
            operator,
            serializer.validated_data["amount"],
            serializer.validated_data["customer_mobile"],
            serializer.validated_data.get("tpin", ""),
            serializer.validated_data.get("idempotency_key", ""),
            payload,
        )
        AuditService.log(request.user, "transaction.execute", tx, request=request)
        return Response(ServiceTransactionSerializer(tx).data, status=201)

    @action(detail=True, methods=["post"])
    def reverse(self, request, pk=None):
        require_admin(request.user)
        tx = RefundService.reverse_success(request.user, self.get_object(), request.data.get("reason", ""), request=request)
        return Response(ServiceTransactionSerializer(tx).data)


class ProviderWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, provider_code):
        provider = Provider.objects.get(code=provider_code)
        event_id = request.data.get("event_id") or request.headers.get("X-Provider-Event") or new_reference("EVT")
        event = WebhookProcessor.process(provider, event_id, request.data)
        return Response(ProviderWebhookEventSerializer(event).data)


class PartnerAPIView(APIView):
    permission_classes = [AllowAny]

    def run_partner(self, request, handler):
        context = None
        try:
            context = validate_partner_request(request)
            response = handler(context)
            log_partner_request(request, context, response.data, response.status_code)
            return response
        except ValidationError as exc:
            response = partner_error(validation_message(exc))
            log_partner_request(request, context, response.data, response.status_code)
            return response


class PayoutInitiateView(PartnerAPIView):
    def post(self, request):
        def handler(context):
            service = find_service("PAYOUT")
            operator = find_operator(service, request.data.get("TransferMode", ""), request.data.get("TransferMode", ""))
            tx = execute_partner_transaction(
                context,
                service,
                operator,
                request.data.get("Amount"),
                request.data.get("MobileNumber", ""),
                request.data.get("OrderId", ""),
                request.data.get("Remarks", "Partner payout"),
                {
                    "payout_pipe": request.data.get("PayoutPipe", "mock"),
                    "beneficiary_name": request.data.get("BeneficiaryName", ""),
                    "account_number": request.data.get("AccountNumber", ""),
                    "ifsc": request.data.get("Ifsc", ""),
                    "bank_name": request.data.get("BankName", ""),
                    "account_type": request.data.get("AccountType", ""),
                    "transfer_mode": request.data.get("TransferMode", ""),
                },
            )
            return partner_success("Transaction Inititated Successfuly", settlement_payload(tx), http_status=201)

        return self.run_partner(request, handler)


class PayinCreatePaymentLinkView(PartnerAPIView):
    def post(self, request):
        def handler(context):
            data = create_payment_link(context.user, request.data.get("Amount"), request.data.get("OrderId"), request.data)
            return partner_success("Payment Link Generated Successfully", data, http_status=201)

        return self.run_partner(request, handler)


class RechargeInitiateView(PartnerAPIView):
    def post(self, request):
        def handler(context):
            service = find_service("MOBILE_RECHARGE")
            operator = find_operator(service, request.data.get("OperatorCode", "") or request.data.get("ProviderId", ""))
            tx = execute_partner_transaction(
                context,
                service,
                operator,
                request.data.get("Amount"),
                request.data.get("MobileNumber") or request.data.get("Number", ""),
                request.data.get("OrderId") or request.data.get("ClientId", ""),
                request.data.get("Remarks", "Partner recharge"),
                {
                    "operator_code": request.data.get("OperatorCode", ""),
                    "provider_id": request.data.get("ProviderId", ""),
                },
            )
            return partner_success("Recharge transaction accepted.", transaction_payload(tx), http_status=201)

        return self.run_partner(request, handler)


class BBPSFetchBillView(PartnerAPIView):
    def post(self, request):
        def handler(context):
            amount = Decimal(str(request.data.get("Amount") or "500.00"))
            data = {
                "reference_id": new_reference("BBPS"),
                "consumer_number": request.data.get("ConsumerNo") or request.data.get("CustomerMobile") or "",
                "customer_name": request.data.get("CustomerName") or "QuickZaps Customer",
                "bill_amount": amount,
                "due_date": timezone.localdate() + timedelta(days=7),
                "status": "FETCHED",
            }
            return partner_success("Bill fetched successfully.", data)

        return self.run_partner(request, handler)


class BBPSPaymentView(PartnerAPIView):
    def post(self, request):
        def handler(context):
            service = find_service("BILLPAY")
            operator = find_operator(service, request.data.get("OperatorCode", ""), request.data.get("ServiceType", ""))
            tx = execute_partner_transaction(
                context,
                service,
                operator,
                request.data.get("Amount"),
                request.data.get("MobileNumber") or request.data.get("ConsumerNo", ""),
                request.data.get("OrderId") or request.data.get("ClientId", ""),
                request.data.get("Remarks", "Partner BBPS payment"),
                {
                    "consumer_number": request.data.get("ConsumerNo", ""),
                    "reference_id": request.data.get("ReferenceId", ""),
                    "service_type": request.data.get("ServiceType", ""),
                },
            )
            return partner_success("BBPS payment accepted.", transaction_payload(tx), http_status=201)

        return self.run_partner(request, handler)


class CMSInitiateView(PartnerAPIView):
    def post(self, request):
        def handler(context):
            transaction_id = request.data.get("OrderId") or new_reference("CMS")
            data = {
                "transaction_id": transaction_id,
                "mobile_number": request.data.get("MobileNumber", ""),
                "status": "PENDING",
                "redirect_url": f"https://cms.quickzaps.local/session/{transaction_id}",
            }
            return partner_success("CMS session created.", data, http_status=201)

        return self.run_partner(request, handler)


class PartnerTransactionStatusView(PartnerAPIView):
    def post(self, request):
        def handler(context):
            order_id = request.data.get("OrderId") or request.data.get("TransactionId")
            if not order_id:
                raise ValidationError("OrderId is required.")
            tx = (
                ServiceTransaction.objects.select_related("initiated_by", "service", "operator", "provider")
                .filter(Q(initiated_by=context.user), Q(idempotency_key=order_id) | Q(reference=order_id))
                .first()
            )
            if not tx:
                raise ValidationError("Transaction not found.")
            return partner_success("Transaction status fetched.", transaction_payload(tx))

        return self.run_partner(request, handler)


class SchemeViewSet(viewsets.ModelViewSet):
    queryset = Scheme.objects.select_related("role").all()
    serializer_class = SchemeSerializer
    filterset_fields = ["role", "active"]
    search_fields = ["name", "remark", "role__name"]


class CommissionRuleViewSet(viewsets.ModelViewSet):
    queryset = CommissionRule.objects.select_related("scheme", "service", "operator").all()
    serializer_class = CommissionRuleSerializer
    filterset_fields = ["scheme", "service", "operator", "active"]
    search_fields = ["scheme__name", "service__name", "operator__name"]


class AdminAPIMarginViewSet(viewsets.ModelViewSet):
    queryset = AdminAPIMargin.objects.select_related("service", "operator", "provider").all()
    serializer_class = AdminAPIMarginSerializer
    filterset_fields = ["service", "operator", "provider", "active"]


class ServicePackageViewSet(viewsets.ModelViewSet):
    queryset = ServicePackage.objects.prefetch_related("slabs").all()
    serializer_class = ServicePackageSerializer
    search_fields = ["name", "description"]


class ServicePackageSlabViewSet(viewsets.ModelViewSet):
    queryset = ServicePackageSlab.objects.select_related("package", "service").all()
    filterset_fields = ["package", "service"]

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return ServicePackageSlabWriteSerializer
        return ServicePackageSlabSerializer


class EmailSettingViewSet(viewsets.ModelViewSet):
    queryset = EmailSetting.objects.all()
    serializer_class = EmailSettingSerializer

    @action(detail=True, methods=["post"], url_path="test")
    def test_email(self, request, pk=None):
        setting = self.get_object()
        setting.last_test_status = f"Configuration accepted at {timezone.now().isoformat()}"
        setting.save(update_fields=["last_test_status", "updated_at"])
        return Response(EmailSettingSerializer(setting).data)


class NewsItemViewSet(viewsets.ModelViewSet):
    queryset = NewsItem.objects.select_related("target_role").all()
    serializer_class = NewsItemSerializer
    filterset_fields = ["target_role", "active"]
    search_fields = ["title", "body"]


class PopupBannerViewSet(viewsets.ModelViewSet):
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    queryset = PopupBanner.objects.all()
    serializer_class = PopupBannerSerializer
    filterset_fields = ["show_type", "active"]


class BulkMessageViewSet(viewsets.ModelViewSet):
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    queryset = BulkMessage.objects.select_related("target_role", "sent_by").all()
    serializer_class = BulkMessageSerializer
    filterset_fields = ["channel", "status", "target_role"]

    @action(detail=True, methods=["post"])
    def send(self, request, pk=None):
        message = NotificationDispatchService.send_bulk(request.user, self.get_object(), request=request)
        return Response(BulkMessageSerializer(message).data)


class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    filterset_fields = ["user", "target_role"]
    search_fields = ["title", "body"]

    def get_queryset(self):
        user = self.request.user
        if is_admin(user):
            return Notification.objects.select_related("user", "target_role", "sent_by").all()
        return Notification.objects.select_related("user", "target_role", "sent_by").filter(Q(user=user) | Q(target_role=user.role))

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        notification = self.get_object()
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at", "updated_at"])
        return Response(NotificationSerializer(notification).data)


class ProviderWebhookEventViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ProviderWebhookEvent.objects.select_related("provider").all()
    serializer_class = ProviderWebhookEventSerializer
    filterset_fields = ["provider", "processing_status"]
    search_fields = ["event_id", "transaction_reference"]


class ReportViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def _transactions(self, request):
        qs = ServiceTransaction.objects.select_related("initiated_by", "service", "operator", "provider").filter(
            initiated_by__in=scoped_user_queryset(request.user)
        )
        status_value = request.query_params.get("status")
        service_id = request.query_params.get("service")
        if status_value:
            qs = qs.filter(status=status_value)
        if service_id:
            qs = qs.filter(service_id=service_id)
        return qs

    @action(detail=False, methods=["get"])
    def dashboard(self, request):
        transactions = self._transactions(request)
        totals = transactions.aggregate(
            total_transactions=Count("id"),
            success=Count("id", filter=Q(status="success")),
            failed=Count("id", filter=Q(status="failed")),
            pending=Count("id", filter=Q(status="pending")),
            total_amount=Sum("amount"),
            total_commission=Sum("commission"),
        )
        service_summary = list(
            transactions.values("service__name", "status")
            .annotate(count=Count("id"), amount=Sum("amount"))
            .order_by("service__name", "status")
        )
        trend = list(
            transactions.annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(count=Count("id"), amount=Sum("amount"))
            .order_by("month")
        )
        wallet_qs = Wallet.objects.filter(user__in=scoped_user_queryset(request.user))
        wallet_totals = wallet_qs.aggregate(available=Sum("available_balance"), hold=Sum("hold_balance"), cap=Sum("cap_balance"))
        pending_counts = {
            "kyc": KYCProfile.objects.filter(user__in=scoped_user_queryset(request.user), status="pending").count(),
            "onboarding": OnboardingApplication.objects.filter(status__in=["pending_parent", "pending_admin"]).count()
            if request.user.is_platform_admin
            else OnboardingApplication.objects.filter(Q(submitted_by=request.user) | Q(agent=request.user) | Q(parent=request.user), status__in=["pending_parent", "pending_admin"]).count(),
            "fund_requests": FundRequest.objects.filter(user__in=scoped_user_queryset(request.user), status="pending").count(),
        }
        news = NewsItem.objects.filter(active=True).filter(Q(target_role__isnull=True) | Q(target_role=request.user.role))[:5]
        return Response(
            {
                "totals": totals,
                "service_summary": service_summary,
                "trend": trend,
                "last_transactions": ServiceTransactionSerializer(transactions.order_by("-created_at")[:10], many=True).data,
                "wallet_totals": wallet_totals,
                "pending_counts": pending_counts,
                "news": NewsItemSerializer(news, many=True).data,
            }
        )

    @action(detail=False, methods=["get"])
    def transactions(self, request):
        qs = self._transactions(request).order_by("-created_at")
        page = self.paginate_queryset(qs) if hasattr(self, "paginate_queryset") else None
        return Response(ServiceTransactionSerializer(page or qs[:100], many=True).data)

    @action(detail=False, methods=["get"])
    def ledger(self, request):
        qs = WalletLedgerEntry.objects.select_related("user", "wallet", "transaction", "transaction__service").filter(
            user__in=scoped_user_queryset(request.user)
        )
        entry_type = request.query_params.get("entry_type")
        if entry_type:
            qs = qs.filter(entry_type=entry_type)
        return Response(WalletLedgerEntrySerializer(qs[:200], many=True).data)

    @action(detail=False, methods=["get"], url_path="wallet-summary")
    def wallet_summary(self, request):
        qs = Wallet.objects.select_related("user", "user__role").filter(user__in=scoped_user_queryset(request.user))
        return Response(WalletSerializer(qs, many=True).data)

    @action(detail=False, methods=["get"], url_path="commission-ledger")
    def commission_ledger(self, request):
        qs = CommissionLedger.objects.select_related("user", "transaction", "transaction__service").filter(user__in=scoped_user_queryset(request.user))
        return Response(CommissionLedgerSerializer(qs[:200], many=True).data)

    @action(detail=False, methods=["get"], url_path="login-history")
    def login_history(self, request):
        qs = LoginHistory.objects.select_related("user").filter(Q(user__in=scoped_user_queryset(request.user)) | Q(user=request.user))
        return Response(LoginHistorySerializer(qs[:200], many=True).data)

    @action(detail=False, methods=["get"], url_path="audit-logs")
    def audit_logs(self, request):
        require_admin(request.user)
        qs = AuditLog.objects.select_related("actor").all()[:200]
        return Response(AuditLogSerializer(qs, many=True).data)

    @action(detail=False, methods=["get"], url_path="day-book")
    def day_book(self, request):
        today = timezone.localdate()
        qs = self._transactions(request).filter(created_at__date=today)
        data = qs.aggregate(
            total_amount=Sum("amount"),
            total_count=Count("id"),
            success_amount=Sum("amount", filter=Q(status="success")),
            success_count=Count("id", filter=Q(status="success")),
            failed_amount=Sum("amount", filter=Q(status="failed")),
            failed_count=Count("id", filter=Q(status="failed")),
            pending_amount=Sum("amount", filter=Q(status="pending")),
            pending_count=Count("id", filter=Q(status="pending")),
            gross_earnings=Sum("charge"),
            net_earnings=Sum("admin_margin"),
        )
        by_date = list(qs.annotate(day=TruncDate("created_at")).values("day").annotate(count=Count("id"), amount=Sum("amount")))
        return Response({"date": today, "summary": data, "by_date": by_date})
