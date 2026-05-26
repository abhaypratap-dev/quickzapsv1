from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    AepsMerchantProfile,
    AdminAPIMargin,
    APIRequestLog,
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


@admin.register(User)
class QuickZapsUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        (
            "QuickZaps",
            {
                "fields": (
                    "mobile",
                    "role",
                    "parent",
                    "status",
                    "kyc_status",
                    "scheme",
                    "service_package",
                    "cap_balance",
                    "company_name",
                    "business_type",
                    "address",
                    "city",
                    "state",
                    "pin_code",
                    "pan_number",
                    "aadhaar_number",
                )
            },
        ),
    )
    list_display = ("mobile", "email", "first_name", "last_name", "role", "status", "kyc_status")
    search_fields = ("mobile", "email", "first_name", "last_name", "company_name")
    list_filter = ("status", "kyc_status", "role")


admin.site.register(Role)
admin.site.register(Service)
admin.site.register(Operator)
admin.site.register(AepsMerchantProfile)
admin.site.register(PartnerAPISetting)
admin.site.register(APIRequestLog)
admin.site.register(ServicePackage)
admin.site.register(ServicePackageSlab)
admin.site.register(Scheme)
admin.site.register(UserSecurityPolicy)
admin.site.register(KYCProfile)
admin.site.register(OnboardingApplication)
admin.site.register(Wallet)
admin.site.register(WalletLedgerEntry)
admin.site.register(FundRequest)
admin.site.register(PaymentGatewayOrder)
admin.site.register(Provider)
admin.site.register(ServiceTransaction)
admin.site.register(CommissionRule)
admin.site.register(AdminAPIMargin)
admin.site.register(CommissionLedger)
admin.site.register(EmailSetting)
admin.site.register(NewsItem)
admin.site.register(PopupBanner)
admin.site.register(BulkMessage)
admin.site.register(Notification)
admin.site.register(ProviderWebhookEvent)
admin.site.register(LoginHistory)
admin.site.register(AuditLog)
