from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AepsViewSet,
    AdminAPIMarginViewSet,
    BBPSFetchBillView,
    BBPSPaymentView,
    BulkMessageViewSet,
    CMSInitiateView,
    CommissionRuleViewSet,
    DeveloperAPIGenerateKeyView,
    DeveloperAPISaveSettingsView,
    DeveloperAPISettingsView,
    EmailSettingViewSet,
    FundRequestViewSet,
    KYCProfileViewSet,
    MeView,
    NewsItemViewSet,
    NotificationViewSet,
    OnboardingApplicationViewSet,
    OperatorViewSet,
    PartnerAPISettingViewSet,
    PartnerTransactionStatusView,
    PayinCreatePaymentLinkView,
    PaymentGatewayOrderViewSet,
    PayoutInitiateView,
    PopupBannerViewSet,
    ProviderViewSet,
    ProviderWebhookEventViewSet,
    ProviderWebhookView,
    RechargeInitiateView,
    ReportViewSet,
    RoleViewSet,
    SchemeViewSet,
    ServicePackageSlabViewSet,
    ServicePackageViewSet,
    ServiceViewSet,
    TransactionViewSet,
    UserViewSet,
    WalletViewSet,
)


router = DefaultRouter()
router.register("roles", RoleViewSet, basename="role")
router.register("users", UserViewSet, basename="user")
router.register("partner-api-settings", PartnerAPISettingViewSet, basename="partner-api-setting")
router.register("aeps", AepsViewSet, basename="aeps")
router.register("kyc", KYCProfileViewSet, basename="kyc")
router.register("onboarding-applications", OnboardingApplicationViewSet, basename="onboarding-application")
router.register("wallets", WalletViewSet, basename="wallet")
router.register("fund-requests", FundRequestViewSet, basename="fund-request")
router.register("gateway-orders", PaymentGatewayOrderViewSet, basename="gateway-order")
router.register("services", ServiceViewSet, basename="service")
router.register("operators", OperatorViewSet, basename="operator")
router.register("providers", ProviderViewSet, basename="provider")
router.register("transactions", TransactionViewSet, basename="transaction")
router.register("schemes", SchemeViewSet, basename="scheme")
router.register("commission-rules", CommissionRuleViewSet, basename="commission-rule")
router.register("api-margins", AdminAPIMarginViewSet, basename="api-margin")
router.register("service-packages", ServicePackageViewSet, basename="service-package")
router.register("service-package-slabs", ServicePackageSlabViewSet, basename="service-package-slab")
router.register("email-settings", EmailSettingViewSet, basename="email-setting")
router.register("news", NewsItemViewSet, basename="news")
router.register("popup-banners", PopupBannerViewSet, basename="popup-banner")
router.register("bulk-messages", BulkMessageViewSet, basename="bulk-message")
router.register("notifications", NotificationViewSet, basename="notification")
router.register("webhook-events", ProviderWebhookEventViewSet, basename="webhook-event")
router.register("reports", ReportViewSet, basename="report")


urlpatterns = [
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("providers/<str:provider_code>/webhook/", ProviderWebhookView.as_view(), name="provider-webhook"),
    path("User/DeveloperAPISettings/DeveloperAPISettings", DeveloperAPISettingsView.as_view(), name="legacy-developer-api-settings-noslash"),
    path("User/DeveloperAPISettings/DeveloperAPISettings/", DeveloperAPISettingsView.as_view(), name="legacy-developer-api-settings"),
    path("User/DeveloperAPISettings/GenerateNewApiKey", DeveloperAPIGenerateKeyView.as_view(), name="legacy-generate-api-key-noslash"),
    path("User/DeveloperAPISettings/GenerateNewApiKey/", DeveloperAPIGenerateKeyView.as_view(), name="legacy-generate-api-key"),
    path("User/DeveloperAPISettings/SaveUpdateApiSettings", DeveloperAPISaveSettingsView.as_view(), name="legacy-save-api-settings-noslash"),
    path("User/DeveloperAPISettings/SaveUpdateApiSettings/", DeveloperAPISaveSettingsView.as_view(), name="legacy-save-api-settings"),
    path("PayoutApi/Payoutinitiate", PayoutInitiateView.as_view(), name="legacy-payout-initiate-noslash"),
    path("PayoutApi/Payoutinitiate/", PayoutInitiateView.as_view(), name="legacy-payout-initiate"),
    path("PayinApi/CreatePaymentLink", PayinCreatePaymentLinkView.as_view(), name="legacy-payin-payment-link-noslash"),
    path("PayinApi/CreatePaymentLink/", PayinCreatePaymentLinkView.as_view(), name="legacy-payin-payment-link"),
    path("RechargeApi/Rechargeinitiate", RechargeInitiateView.as_view(), name="legacy-recharge-initiate-noslash"),
    path("RechargeApi/Rechargeinitiate/", RechargeInitiateView.as_view(), name="legacy-recharge-initiate"),
    path("BBPSApi/FetchBill", BBPSFetchBillView.as_view(), name="legacy-bbps-fetch-noslash"),
    path("BBPSApi/FetchBill/", BBPSFetchBillView.as_view(), name="legacy-bbps-fetch"),
    path("BBPSApi/PayBill", BBPSPaymentView.as_view(), name="legacy-bbps-pay-noslash"),
    path("BBPSApi/PayBill/", BBPSPaymentView.as_view(), name="legacy-bbps-pay"),
    path("CMSApi/Initiate", CMSInitiateView.as_view(), name="legacy-cms-initiate-noslash"),
    path("CMSApi/Initiate/", CMSInitiateView.as_view(), name="legacy-cms-initiate"),
    path("TransactionApi/Status", PartnerTransactionStatusView.as_view(), name="legacy-transaction-status-noslash"),
    path("TransactionApi/Status/", PartnerTransactionStatusView.as_view(), name="legacy-transaction-status"),
    path("", include(router.urls)),
]
