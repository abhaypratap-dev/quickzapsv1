from decimal import Decimal

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import (
    AdminAPIMargin,
    CommissionRule,
    KYCProfile,
    NewsItem,
    Operator,
    PartnerAPISetting,
    PopupBanner,
    Provider,
    Role,
    Scheme,
    Service,
    ServicePackage,
    ServicePackageSlab,
    User,
    UserSecurityPolicy,
    Wallet,
    WalletLedgerEntry,
)
from core.services import TransactionExecutionService, WalletLedgerService


ROLE_BLUEPRINT = {
    "SUPER_ADMIN": {
        "name": "Super Admin",
        "level": 0,
        "children": ["ADMIN", "SDBR", "DBR", "RETAILER", "API_USER", "STATE_HEAD", "ZBP", "SUPER_DISTRIBUTOR", "MD", "AD"],
        "permissions": ["*"],
    },
    "ADMIN": {
        "name": "Admin",
        "level": 1,
        "children": ["SDBR", "DBR", "RETAILER", "API_USER", "STATE_HEAD", "ZBP", "SUPER_DISTRIBUTOR", "MD", "AD"],
        "permissions": [
            "user.view",
            "user.create",
            "user.update",
            "user.delete",
            "user.restore",
            "user.upgrade",
            "kyc.view",
            "kyc.approve",
            "kyc.reject",
            "onboarding.approve",
            "wallet.view",
            "wallet.adjust.admin",
            "wallet.fund.approve",
            "commission.configure",
            "report.admin.view",
            "provider.configure",
            "notification.send",
        ],
    },
    "STATE_HEAD": {
        "name": "State Head",
        "level": 2,
        "children": ["ZBP", "SUPER_DISTRIBUTOR", "MD", "AD", "RETAILER"],
        "permissions": [
            "user.view.downline",
            "user.create.downline",
            "wallet.view.self",
            "wallet.transfer.downline",
            "service.billpay",
            "service.recharge",
            "service.dmt",
            "service.payout",
            "commission.ledger.self",
            "report.downline.view",
        ],
    },
    "ZBP": {"name": "ZBP", "level": 3, "children": ["SUPER_DISTRIBUTOR", "MD", "AD", "RETAILER"], "permissions": []},
    "SDBR": {"name": "Super Distributor", "level": 4, "children": ["DBR", "RETAILER"], "permissions": ["onboarding.approve", "user.view.downline", "report.downline.view"]},
    "DBR": {"name": "Distributor", "level": 5, "children": ["RETAILER"], "permissions": ["onboarding.approve", "user.view.downline", "report.downline.view"]},
    "SUPER_DISTRIBUTOR": {"name": "Super Distributor", "level": 4, "children": ["MD", "AD", "RETAILER"], "permissions": []},
    "MD": {"name": "Master Distributor", "level": 5, "children": ["AD", "RETAILER"], "permissions": []},
    "AD": {"name": "Area Distributor", "level": 6, "children": ["RETAILER"], "permissions": []},
    "RETAILER": {
        "name": "Retailer",
        "level": 7,
        "children": [],
        "permissions": [
            "wallet.view.self",
            "wallet.fund.request",
            "service.billpay",
            "service.recharge",
            "service.dmt",
            "service.payout",
            "service.account.verify",
            "commission.ledger.self",
            "report.self.view",
        ],
    },
    "API_USER": {
        "name": "API User",
        "level": 7,
        "children": [],
        "permissions": [
            "api.key.manage",
            "service.billpay",
            "service.recharge",
            "service.dmt",
            "service.payout",
            "service.account.verify",
            "report.self.view",
        ],
    },
}


class Command(BaseCommand):
    help = "Seed QuickZaps roles, services, providers, demo users, wallets, commissions, and transactions."

    @transaction.atomic
    def handle(self, *args, **options):
        roles = {}
        for code, data in ROLE_BLUEPRINT.items():
            role, _ = Role.objects.update_or_create(
                code=code,
                defaults={
                    "name": data["name"],
                    "level": data["level"],
                    "can_create_downline": bool(data["children"]),
                    "can_transact": code not in {"ADMIN"},
                    "can_earn_commission": code not in {"ADMIN"},
                    "permissions": data["permissions"],
                    "active": True,
                },
            )
            roles[code] = role
        for code, data in ROLE_BLUEPRINT.items():
            roles[code].child_roles.set([roles[child] for child in data["children"]])

        services = {}
        service_rows = [
            ("BILLPAY", "Utility Bill Payment", "billpay", True, True, "10", "50000"),
            ("MOBILE_RECHARGE", "Mobile Recharge", "recharge", True, True, "10", "10000"),
            ("DMT", "Domestic Money Transfer", "dmt", True, True, "100", "25000"),
            ("EXPRESS_MONEY", "Express Money", "express_money", True, True, "100", "25000"),
            ("PAYOUT", "Payout", "payout", True, True, "100", "100000"),
            ("ACCOUNT_VERIFY", "Account Verification", "account_verify", True, True, "1", "1000"),
            ("AEPS_CASH_WITHDRAWAL", "AEPS Cash Withdrawal", "aeps", True, False, "100", "10000"),
            ("AEPS_BALANCE_ENQUIRY", "AEPS Balance Enquiry", "aeps", True, False, "0", "0"),
            ("AEPS_MINI_STATEMENT", "AEPS Mini Statement", "aeps", True, False, "0", "0"),
            ("AADHAAR_PAY", "Aadhaar Pay", "aeps", True, False, "1", "50000"),
            ("AEPS_CASH_DEPOSIT", "AEPS Cash Deposit", "aeps", True, False, "100", "50000"),
        ]
        for code, name, category, requires_kyc, tpin_required, min_amount, max_amount in service_rows:
            service, _ = Service.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "category": category,
                    "requires_kyc": requires_kyc,
                    "tpin_required": tpin_required,
                    "min_amount": Decimal(min_amount),
                    "max_amount": Decimal(max_amount),
                    "active": True,
                },
            )
            services[code] = service

        operators = {}
        operator_rows = [
            ("BILLPAY", "ELECTRICITY", "Electricity"),
            ("BILLPAY", "WATER", "Water"),
            ("BILLPAY", "FASTAG", "FASTag"),
            ("BILLPAY", "INSURANCE", "Insurance"),
            ("MOBILE_RECHARGE", "AIRTEL_PREPAID", "Airtel Prepaid"),
            ("MOBILE_RECHARGE", "JIO_PREPAID", "Jio Prepaid"),
            ("MOBILE_RECHARGE", "VI_PREPAID", "Vi (Vodafone Idea) Prepaid"),
            ("MOBILE_RECHARGE", "BSNL_PREPAID", "BSNL Prepaid"),
            ("MOBILE_RECHARGE", "AIRTEL_DTH", "Airtel Digital TV"),
            ("MOBILE_RECHARGE", "TATA_PLAY", "Tata Play (Tata Sky)"),
            ("MOBILE_RECHARGE", "DISH_TV", "Dish TV"),
            ("DMT", "BANK_TRANSFER", "Bank Transfer"),
            ("EXPRESS_MONEY", "EXPRESS_TRANSFER", "Express Transfer"),
            ("PAYOUT", "IMPS", "IMPS"),
            ("PAYOUT", "NEFT", "NEFT"),
            ("PAYOUT", "UPI", "UPI"),
            ("ACCOUNT_VERIFY", "BANK_ACCOUNT", "Bank Account"),
            ("AEPS_CASH_WITHDRAWAL", "CW", "Cash Withdrawal"),
            ("AEPS_BALANCE_ENQUIRY", "BE", "Balance Enquiry"),
            ("AEPS_MINI_STATEMENT", "MS", "Mini Statement"),
            ("AADHAAR_PAY", "M", "Aadhaar Pay"),
            ("AEPS_CASH_DEPOSIT", "CD", "Cash Deposit"),
        ]
        for service_code, code, name in operator_rows:
            operator, _ = Operator.objects.update_or_create(
                service=services[service_code],
                code=code,
                defaults={"name": name, "active": True},
            )
            operators[code] = operator

        package, _ = ServicePackage.objects.update_or_create(
            name="Standard Service Package",
            defaults={"description": "Default enabled package for seeded QuickZaps users.", "active": True},
        )
        for service in services.values():
            ServicePackageSlab.objects.update_or_create(
                package=package,
                service=service,
                defaults={"service_amount": Decimal("0.0000")},
            )

        providers = {}
        if Provider.objects.filter(code="FINGPAY_AEPS_UAT").exists() and not Provider.objects.filter(code="FINGPAY_AEPS").exists():
            Provider.objects.filter(code="FINGPAY_AEPS_UAT").update(code="FINGPAY_AEPS")
        provider_rows = [
            ("MOCK_BILLPAY", "Sandbox BillPay Provider", "utility"),
            ("MOCK_RECHARGE", "Sandbox Recharge Provider", "recharge"),
            ("MOCK_DMT", "Sandbox DMT Provider", "dmt"),
            ("MOCK_PAYOUT", "Sandbox Payout Provider", "payout"),
            ("MOCK_VERIFY", "Sandbox Verification Provider", "verification"),
            ("MOCK_PAYMENT_GATEWAY", "Sandbox Payment Gateway", "payment_gateway"),
            ("FINGPAY_AEPS", "Fingpay AEPS", "aeps"),
        ]
        for code, name, provider_type in provider_rows:
            base_url = getattr(settings, "FINGPAY_AEPS_BASE_URL", "https://fingpayap.tapits.in") if provider_type == "aeps" else f"https://sandbox-provider.local/{provider_type}"
            provider, _ = Provider.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "provider_type": provider_type,
                    "base_url": base_url,
                    "active": True,
                    "supports_webhook": True,
                    "supports_status_polling": True,
                    "health_status": "healthy",
                    "config": {"mode": "live"} if provider_type == "aeps" else {},
                },
            )
            providers[code] = provider

        schemes = {}
        for role in roles.values():
            scheme, _ = Scheme.objects.update_or_create(
                role=role,
                name=f"{role.name} Standard",
                defaults={"remark": "Seeded commission scheme for local demo.", "active": True},
            )
            schemes[role.code] = scheme

        for scheme in schemes.values():
            for service in services.values():
                CommissionRule.objects.update_or_create(
                    scheme=scheme,
                    service=service,
                    operator=None,
                    defaults={
                        "commission_value": Decimal("0.5000") if service.category != "account_verify" else Decimal("1.0000"),
                        "commission_type": "percent" if service.category != "account_verify" else "fixed",
                        "surcharge_value": Decimal("1.0000") if service.category != "account_verify" else Decimal("2.0000"),
                        "surcharge_type": "fixed",
                        "tds_percent": Decimal("5.0000"),
                        "gst_percent": Decimal("18.0000"),
                        "active": True,
                    },
                )

        AdminAPIMargin.objects.update_or_create(
            service=services["BILLPAY"],
            operator=None,
            provider=providers["MOCK_BILLPAY"],
            defaults={"margin_value": Decimal("0.3000"), "margin_type": "percent", "active": True},
        )

        admin = self.ensure_user(
            mobile="9000000000",
            email="admin@quickzaps.local",
            first_name="QuickZaps",
            last_name="Admin",
            role=roles["SUPER_ADMIN"],
            parent=None,
            scheme=schemes["SUPER_ADMIN"],
            package=package,
            password="Admin@12345",
            wallet_credit=Decimal("100000.0000"),
            status="active",
        )
        sdbr = self.ensure_user(
            mobile="9000000005",
            email="sdbr@quickzaps.local",
            first_name="Demo",
            last_name="SDBR",
            role=roles["SDBR"],
            parent=admin,
            scheme=schemes["SDBR"],
            package=package,
            password="Demo@12345",
            wallet_credit=Decimal("30000.0000"),
            status="active",
        )
        dbr = self.ensure_user(
            mobile="9000000006",
            email="dbr@quickzaps.local",
            first_name="Demo",
            last_name="DBR",
            role=roles["DBR"],
            parent=sdbr,
            scheme=schemes["DBR"],
            package=package,
            password="Demo@12345",
            wallet_credit=Decimal("20000.0000"),
            status="active",
        )
        state_head = self.ensure_user(
            mobile="9000000001",
            email="statehead@quickzaps.local",
            first_name="Demo",
            last_name="State Head",
            role=roles["STATE_HEAD"],
            parent=admin,
            scheme=schemes["STATE_HEAD"],
            package=package,
            password="Demo@12345",
            wallet_credit=Decimal("25000.0000"),
            status="active",
        )
        md = self.ensure_user(
            mobile="9000000002",
            email="md@quickzaps.local",
            first_name="Demo",
            last_name="MD",
            role=roles["MD"],
            parent=state_head,
            scheme=schemes["MD"],
            package=package,
            password="Demo@12345",
            wallet_credit=Decimal("15000.0000"),
            status="active",
        )
        retailer = self.ensure_user(
            mobile="9000000003",
            email="retailer@quickzaps.local",
            first_name="Demo",
            last_name="Retailer",
            role=roles["RETAILER"],
            parent=dbr,
            scheme=schemes["RETAILER"],
            package=package,
            password="Demo@12345",
            wallet_credit=Decimal("10000.0000"),
            status="active",
        )
        api_user = self.ensure_user(
            mobile="9000000004",
            email="apiuser@quickzaps.local",
            first_name="Demo",
            last_name="API User",
            role=roles["API_USER"],
            parent=admin,
            scheme=schemes["API_USER"],
            package=package,
            password="Demo@12345",
            wallet_credit=Decimal("5000.0000"),
            status="active",
        )
        self.ensure_api_setting(api_user)

        NewsItem.objects.update_or_create(
            title="Sandbox providers are enabled",
            defaults={
                "body": "Local demo transactions route through QuickZaps sandbox providers while wallets and ledgers use the real application flow.",
                "target_role": None,
                "active": True,
                "priority": 1,
            },
        )
        PopupBanner.objects.update_or_create(
            title="QuickZaps local demo",
            defaults={
                "show_type": "dashboard",
                "active": True,
                "description": "Dashboard banner configured from the database.",
                "display_frequency": "once_per_login",
            },
        )

        self.ensure_demo_transactions(retailer, services, operators)
        self.stdout.write(self.style.SUCCESS("QuickZaps demo data seeded."))

    def ensure_user(self, mobile, email, first_name, last_name, role, parent, scheme, package, password, wallet_credit, status):
        user, created = User.objects.get_or_create(
            username=mobile,
            defaults={
                "mobile": mobile,
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "role": role,
                "parent": parent,
                "scheme": scheme,
                "service_package": package,
                "status": status,
                "is_active": status == "active",
                "kyc_status": "approved",
                "company_name": f"{first_name} {last_name} Services",
                "business_type": "Retail services",
                "address": "QuickZaps Demo Address",
                "city": "Mumbai",
                "state": "Maharashtra",
                "pin_code": "400001",
                "pan_number": f"QZPAN{mobile[-4:]}",
                "aadhaar_number": f"99990000{mobile[-4:]}",
                "tpin_hash": make_password("123456"),
                "mpin_hash": make_password("1234"),
            },
        )
        if not created:
            user.email = email
            user.first_name = first_name
            user.last_name = last_name
            user.role = role
            user.parent = parent
            user.scheme = scheme
            user.service_package = package
            user.status = status
            user.is_active = status == "active"
            user.kyc_status = "approved"
            user.tpin_hash = user.tpin_hash or make_password("123456")
            user.mpin_hash = user.mpin_hash or make_password("1234")
        user.set_password(password)
        user.save()

        wallet, _ = Wallet.objects.get_or_create(user=user, defaults={"cap_balance": user.cap_balance})
        UserSecurityPolicy.objects.update_or_create(
            user=user,
            defaults={
                "transaction_tpin_required": True,
                "login_sms_otp_enabled": False,
                "login_email_otp_enabled": False,
                "login_whatsapp_otp_enabled": False,
                "login_mpin_enabled": True,
                "aadhaar_kyc_required": True,
                "pan_kyc_required": True,
            },
        )
        KYCProfile.objects.update_or_create(
            user=user,
            defaults={
                "status": "approved",
                "pan_number": user.pan_number,
                "aadhaar_number": user.aadhaar_number,
            },
        )
        ref = f"SEED-{mobile}"
        if not WalletLedgerEntry.objects.filter(wallet=wallet, transaction_ref=ref).exists():
            WalletLedgerService.credit(user, wallet_credit, reference=ref, remarks="Seed opening balance")
        return user

    def ensure_api_setting(self, user):
        if settings.PARTNER_API_DUMMY_MODE:
            return None
        setting, _ = PartnerAPISetting.objects.get_or_create(user=user)
        if not setting.active:
            setting.active = True
            setting.save(update_fields=["active", "updated_at"])
        return setting

    def ensure_demo_transactions(self, retailer, services, operators):
        demos = [
            ("seed-success-billpay", "BILLPAY", "ELECTRICITY", "450.0000", "9876543210", "success", "Seed success bill payment"),
            ("seed-failed-recharge", "MOBILE_RECHARGE", "AIRTEL_PREPAID", "199.0000", "9876500000", "failed", "Seed failed recharge"),
            ("seed-pending-dmt", "DMT", "BANK_TRANSFER", "750.0000", "9876599999", "pending", "Seed pending DMT"),
        ]
        for key, service_code, operator_code, amount, mobile, outcome, description in demos:
            if retailer.transactions.filter(idempotency_key=key).exists():
                continue
            TransactionExecutionService.execute(
                retailer,
                services[service_code],
                operators[operator_code],
                Decimal(amount),
                mobile,
                tpin="123456",
                idempotency_key=key,
                payload={"description": f"{description} ({outcome})"},
            )
