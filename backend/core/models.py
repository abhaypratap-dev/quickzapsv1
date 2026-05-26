from decimal import Decimal
from secrets import token_hex

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


def generate_api_key():
    return token_hex(24)


class Role(TimeStampedModel):
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=80)
    level = models.PositiveSmallIntegerField(default=99)
    can_create_downline = models.BooleanField(default=False)
    can_transact = models.BooleanField(default=True)
    can_earn_commission = models.BooleanField(default=True)
    child_roles = models.ManyToManyField("self", symmetrical=False, blank=True)
    permissions = models.JSONField(default=list, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["level", "name"]

    def __str__(self):
        return self.name

    @property
    def is_admin_role(self):
        return self.code in {"SUPER_ADMIN", "ADMIN"}


class Service(TimeStampedModel):
    CATEGORY_CHOICES = [
        ("aeps", "AEPS"),
        ("billpay", "Utility Bill Payment"),
        ("recharge", "Recharge"),
        ("dmt", "DMT"),
        ("express_money", "Express Money"),
        ("payout", "Payout"),
        ("account_verify", "Account Verification"),
    ]

    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=120)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    active = models.BooleanField(default=True)
    requires_kyc = models.BooleanField(default=True)
    tpin_required = models.BooleanField(default=True)
    min_amount = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal("1.0000"))
    max_amount = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal("50000.0000"))

    class Meta:
        ordering = ["category", "name"]

    def __str__(self):
        return self.name


class Operator(TimeStampedModel):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="operators")
    code = models.CharField(max_length=60)
    name = models.CharField(max_length=120)
    active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("service", "code")]
        ordering = ["service__name", "name"]

    def __str__(self):
        return f"{self.service.name} - {self.name}"


class ServicePackage(TimeStampedModel):
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class ServicePackageSlab(TimeStampedModel):
    package = models.ForeignKey(ServicePackage, on_delete=models.CASCADE, related_name="slabs")
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    service_amount = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0.0000"))

    class Meta:
        unique_together = [("package", "service")]


class Scheme(TimeStampedModel):
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="schemes")
    name = models.CharField(max_length=120)
    remark = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("role", "name")]
        ordering = ["role__level", "name"]

    def __str__(self):
        return f"{self.role.name} - {self.name}"


class User(AbstractUser):
    STATUS_CHOICES = [
        ("signup", "Signup Review"),
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("deleted", "Deleted"),
    ]
    KYC_CHOICES = [
        ("not_submitted", "Not Submitted"),
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("reupload_requested", "Reupload Requested"),
    ]

    mobile = models.CharField(max_length=20, unique=True)
    email = models.EmailField(unique=True)
    role = models.ForeignKey(Role, on_delete=models.PROTECT, null=True, blank=True, related_name="users")
    parent = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="children")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="signup")
    kyc_status = models.CharField(max_length=30, choices=KYC_CHOICES, default="not_submitted")
    scheme = models.ForeignKey(Scheme, on_delete=models.PROTECT, null=True, blank=True)
    service_package = models.ForeignKey(ServicePackage, on_delete=models.PROTECT, null=True, blank=True)
    cap_balance = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0.0000"))
    company_name = models.CharField(max_length=160, blank=True)
    business_type = models.CharField(max_length=80, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=80, blank=True)
    state = models.CharField(max_length=80, blank=True)
    pin_code = models.CharField(max_length=12, blank=True)
    dob = models.DateField(null=True, blank=True)
    pan_number = models.CharField(max_length=20, blank=True)
    aadhaar_number = models.CharField(max_length=20, blank=True)
    mpin_hash = models.CharField(max_length=128, blank=True)
    tpin_hash = models.CharField(max_length=128, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    REQUIRED_FIELDS = ["email", "mobile"]

    class Meta:
        ordering = ["role__level", "first_name", "mobile"]
        indexes = [
            models.Index(fields=["status", "role"]),
            models.Index(fields=["parent", "status"]),
            models.Index(fields=["mobile"]),
        ]

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.mobile})"

    @property
    def is_platform_admin(self):
        return bool(self.role and self.role.is_admin_role)

    def soft_delete(self):
        self.status = "deleted"
        self.is_active = False
        self.deleted_at = timezone.now()
        self.save(update_fields=["status", "is_active", "deleted_at", "updated_at"])


class UserSecurityPolicy(TimeStampedModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="security_policy")
    login_sms_otp_enabled = models.BooleanField(default=False)
    login_email_otp_enabled = models.BooleanField(default=False)
    login_whatsapp_otp_enabled = models.BooleanField(default=False)
    login_mpin_enabled = models.BooleanField(default=False)
    transaction_tpin_required = models.BooleanField(default=True)
    change_mpin_allowed = models.BooleanField(default=True)
    change_tpin_allowed = models.BooleanField(default=True)
    aadhaar_kyc_required = models.BooleanField(default=True)
    pan_kyc_required = models.BooleanField(default=True)
    cap_balance_enforced = models.BooleanField(default=False)


class PartnerAPISetting(TimeStampedModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="partner_api_setting")
    api_key = models.CharField(max_length=128, unique=True, db_index=True, default=generate_api_key)
    allowed_ip = models.GenericIPAddressField(null=True, blank=True)
    allowed_ip2 = models.GenericIPAddressField(null=True, blank=True)
    webhook_url = models.URLField(blank=True)
    active = models.BooleanField(default=True)
    generated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["user__mobile"]

    def rotate_key(self):
        self.api_key = generate_api_key()
        self.generated_at = timezone.now()
        self.save(update_fields=["api_key", "generated_at", "updated_at"])
        return self.api_key

    def __str__(self):
        return f"{self.user.mobile} API setting"


class APIRequestLog(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="api_request_logs")
    request_id = models.CharField(max_length=120, blank=True, db_index=True)
    api_key_prefix = models.CharField(max_length=16, blank=True)
    path = models.CharField(max_length=240)
    method = models.CharField(max_length=12)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    status_code = models.PositiveSmallIntegerField(default=200)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["request_id"]),
            models.Index(fields=["status_code", "created_at"]),
        ]


class KYCProfile(TimeStampedModel):
    STATUS_CHOICES = User.KYC_CHOICES

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="kyc_profile")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="not_submitted")
    pan_number = models.CharField(max_length=20, blank=True)
    aadhaar_number = models.CharField(max_length=20, blank=True)
    aadhaar_front = models.FileField(upload_to="kyc/aadhaar_front/", blank=True, null=True)
    aadhaar_back = models.FileField(upload_to="kyc/aadhaar_back/", blank=True, null=True)
    pan_image = models.FileField(upload_to="kyc/pan/", blank=True, null=True)
    shop_image = models.FileField(upload_to="kyc/shop/", blank=True, null=True)
    user_photo = models.FileField(upload_to="kyc/user_photo/", blank=True, null=True)
    reviewer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="kyc_reviews")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    def __str__(self):
        return f"KYC {self.user.mobile}: {self.status}"


class AepsMerchantProfile(TimeStampedModel):
    STATUS_CHOICES = [
        ("not_started", "Not Started"),
        ("onboarding_pending", "Onboarding Pending"),
        ("onboarded", "Onboarded"),
        ("active", "Active"),
        ("rejected", "Rejected"),
        ("suspended", "Suspended"),
    ]
    KYC_STATUS_CHOICES = [
        ("not_started", "Not Started"),
        ("otp_sent", "OTP Sent"),
        ("otp_validated", "OTP Validated"),
        ("biometric_pending", "Biometric Pending"),
        ("verified", "Verified"),
        ("failed", "Failed"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="aeps_profile")
    merchant_login_id = models.CharField(max_length=80, unique=True, db_index=True)
    merchant_phone_number = models.CharField(max_length=20)
    super_merchant_id = models.PositiveIntegerField(default=0)
    fingpay_merchant_status = models.BooleanField(default=False)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="not_started", db_index=True)
    kyc_status = models.CharField(max_length=30, choices=KYC_STATUS_CHOICES, default="not_started", db_index=True)

    device_imei = models.CharField(max_length=80, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)

    merchant_state = models.PositiveIntegerField(null=True, blank=True)
    merchant_city_name = models.CharField(max_length=80, blank=True)
    merchant_district_name = models.CharField(max_length=80, blank=True)
    merchant_pin_code = models.CharField(max_length=12, blank=True)
    company_legal_name = models.CharField(max_length=160, blank=True)
    company_type = models.PositiveIntegerField(null=True, blank=True)
    company_bank_name = models.CharField(max_length=120, blank=True)
    bank_ifsc_code = models.CharField(max_length=20, blank=True)
    settlement_account_last4 = models.CharField(max_length=4, blank=True)
    bank_account_name = models.CharField(max_length=160, blank=True)

    primary_key_id = models.PositiveIntegerField(null=True, blank=True)
    encode_fp_txn_id = models.CharField(max_length=160, blank=True)
    onboarding_response = models.JSONField(default=dict, blank=True)
    ekyc_response = models.JSONField(default=dict, blank=True)
    last_provider_message = models.CharField(max_length=240, blank=True)
    rejection_reason = models.TextField(blank=True)
    last_onboarded_at = models.DateTimeField(null=True, blank=True)
    last_ekyc_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["user__mobile"]
        indexes = [
            models.Index(fields=["status", "kyc_status"]),
            models.Index(fields=["merchant_login_id"]),
        ]

    def __str__(self):
        return f"AEPS {self.user.mobile}: {self.status}/{self.kyc_status}"

    @property
    def can_access_services(self):
        return self.status == "active" and self.kyc_status == "verified"

    @property
    def next_step(self):
        if self.can_access_services:
            return "services"
        if self.status in {"onboarded", "active"}:
            return "ekyc"
        return "merchant_onboarding"


class OnboardingApplication(TimeStampedModel):
    ROLE_CHOICES = [
        ("SDBR", "Super Distributor"),
        ("DBR", "Distributor"),
        ("RETAILER", "Retailer"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending_parent", "Pending Parent Approval"),
        ("pending_admin", "Pending Admin Approval"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("created", "User Created"),
    ]

    requested_role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="pending_admin", db_index=True)
    submitted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="submitted_onboarding_applications")
    agent = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="agent_onboarding_applications")
    parent = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="parent_onboarding_applications")
    parent_approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="parent_approved_onboarding")
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_onboarding_applications")
    created_user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="source_onboarding_application")
    direct_to_admin = models.BooleanField(default=False)

    mobile = models.CharField(max_length=20, db_index=True)
    email = models.EmailField()
    full_name = models.CharField(max_length=160)
    dob = models.DateField()
    aadhaar_number = models.CharField(max_length=20)
    pan_number = models.CharField(max_length=20)

    pan_verification = models.JSONField(default=dict, blank=True)
    aadhaar_verification = models.JSONField(default=dict, blank=True)
    bank_verification = models.JSONField(default=dict, blank=True)
    gst_verification = models.JSONField(default=dict, blank=True)
    udyam_verification = models.JSONField(default=dict, blank=True)
    verification_mode = models.CharField(max_length=20, default="dummy")

    live_photo = models.FileField(upload_to="onboarding/live_photo/", blank=True, null=True)
    live_photo_geo = models.JSONField(default=dict, blank=True)
    shop_photo = models.FileField(upload_to="onboarding/shop_photo/", blank=True, null=True)
    shop_photo_geo = models.JSONField(default=dict, blank=True)
    agent_photo = models.FileField(upload_to="onboarding/agent_photo/", blank=True, null=True)
    agent_photo_geo = models.JSONField(default=dict, blank=True)

    account_holder_name = models.CharField(max_length=160)
    bank_name = models.CharField(max_length=120, blank=True)
    account_number = models.CharField(max_length=40)
    ifsc = models.CharField(max_length=20)
    upi_id = models.CharField(max_length=120, blank=True)
    bank_proof = models.FileField(upload_to="onboarding/bank_proof/", blank=True, null=True)
    rpd_reference_id = models.CharField(max_length=120, blank=True)
    rpd_link = models.URLField(blank=True)
    rpd_status = models.CharField(max_length=40, blank=True)

    business_name = models.CharField(max_length=160)
    business_type = models.CharField(max_length=80, blank=True)
    gst_number = models.CharField(max_length=30, blank=True)
    udyam_number = models.CharField(max_length=40, blank=True)
    business_address = models.TextField()
    city = models.CharField(max_length=80)
    state = models.CharField(max_length=80)
    pin_code = models.CharField(max_length=12)
    business_photo = models.FileField(upload_to="onboarding/business_photo/", blank=True, null=True)
    gst_document = models.FileField(upload_to="onboarding/gst_document/", blank=True, null=True)
    udyam_document = models.FileField(upload_to="onboarding/udyam_document/", blank=True, null=True)

    review_note = models.TextField(blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "requested_role"]),
            models.Index(fields=["mobile"]),
            models.Index(fields=["parent", "status"]),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.mobile}) - {self.requested_role}"


class Wallet(TimeStampedModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="wallet")
    available_balance = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0.0000"))
    hold_balance = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0.0000"))
    cap_balance = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0.0000"))

    class Meta:
        indexes = [models.Index(fields=["user"])]

    @property
    def total_balance(self):
        return self.available_balance + self.hold_balance

    def __str__(self):
        return f"{self.user.mobile}: {self.available_balance}"


class Provider(TimeStampedModel):
    TYPE_CHOICES = [
        ("aeps", "AEPS"),
        ("utility", "Utility"),
        ("recharge", "Recharge"),
        ("dmt", "DMT"),
        ("payout", "Payout"),
        ("payment_gateway", "Payment Gateway"),
        ("verification", "Verification"),
        ("notification", "Notification"),
    ]
    STATUS_CHOICES = [("healthy", "Healthy"), ("degraded", "Degraded"), ("down", "Down")]

    code = models.CharField(max_length=60, unique=True)
    name = models.CharField(max_length=120)
    provider_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    base_url = models.URLField(blank=True)
    active = models.BooleanField(default=True)
    supports_webhook = models.BooleanField(default=True)
    supports_status_polling = models.BooleanField(default=True)
    health_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="healthy")
    config = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return self.name


class ServiceTransaction(TimeStampedModel):
    STATUS_CHOICES = [
        ("quoted", "Quoted"),
        ("pending", "Pending"),
        ("success", "Success"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
        ("reversed", "Reversed"),
        ("manual_review", "Manual Review"),
    ]

    reference = models.CharField(max_length=40, unique=True)
    initiated_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="transactions")
    service = models.ForeignKey(Service, on_delete=models.PROTECT)
    operator = models.ForeignKey(Operator, on_delete=models.PROTECT, null=True, blank=True)
    provider = models.ForeignKey(Provider, on_delete=models.PROTECT, null=True, blank=True)
    customer_mobile = models.CharField(max_length=20, blank=True)
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    charge = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0.0000"))
    commission = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0.0000"))
    admin_margin = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0.0000"))
    total_debit = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0.0000"))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    idempotency_key = models.CharField(max_length=120, blank=True)
    provider_reference = models.CharField(max_length=120, blank=True)
    provider_status = models.CharField(max_length=40, blank=True)
    description = models.CharField(max_length=240, blank=True)
    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["initiated_by", "created_at"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["service", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["initiated_by", "idempotency_key"],
                condition=~models.Q(idempotency_key=""),
                name="uniq_transaction_idempotency_per_user",
            )
        ]

    def __str__(self):
        return f"{self.reference} {self.status}"


class WalletLedgerEntry(TimeStampedModel):
    ENTRY_CHOICES = [
        ("credit", "Credit"),
        ("debit", "Debit"),
        ("hold", "Hold"),
        ("hold_capture", "Hold Capture"),
        ("hold_release", "Hold Release"),
        ("refund", "Refund"),
        ("commission", "Commission"),
        ("commission_reversal", "Commission Reversal"),
        ("adjustment", "Adjustment"),
    ]

    wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT, related_name="ledger_entries")
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="ledger_entries")
    transaction = models.ForeignKey(ServiceTransaction, on_delete=models.PROTECT, null=True, blank=True, related_name="ledger_entries")
    entry_type = models.CharField(max_length=30, choices=ENTRY_CHOICES)
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    opening_balance = models.DecimalField(max_digits=18, decimal_places=4)
    closing_balance = models.DecimalField(max_digits=18, decimal_places=4)
    transaction_ref = models.CharField(max_length=80, blank=True)
    remarks = models.CharField(max_length=240, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_ledger_entries")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["wallet", "created_at"]),
            models.Index(fields=["transaction_ref"]),
            models.Index(fields=["entry_type", "created_at"]),
        ]


class FundRequest(TimeStampedModel):
    STATUS_CHOICES = [("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")]
    METHOD_CHOICES = [("bank", "Bank Transfer"), ("upi", "UPI"), ("cash", "Cash"), ("gateway", "Gateway")]

    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="fund_requests")
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default="bank")
    payment_reference = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    note = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_fund_requests")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]


class PaymentGatewayOrder(TimeStampedModel):
    STATUS_CHOICES = [("created", "Created"), ("success", "Success"), ("failed", "Failed")]

    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="gateway_orders")
    reference = models.CharField(max_length=40, unique=True)
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="created")
    provider_reference = models.CharField(max_length=120, blank=True)
    payload = models.JSONField(default=dict, blank=True)


class CommissionRule(TimeStampedModel):
    TYPE_CHOICES = [("fixed", "Fixed"), ("percent", "Percent")]

    scheme = models.ForeignKey(Scheme, on_delete=models.CASCADE, related_name="commission_rules")
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    operator = models.ForeignKey(Operator, on_delete=models.CASCADE, null=True, blank=True)
    commission_value = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0.0000"))
    commission_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="fixed")
    surcharge_value = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0.0000"))
    surcharge_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="fixed")
    tds_percent = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal("0.0000"))
    gst_percent = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal("0.0000"))
    active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("scheme", "service", "operator")]


class AdminAPIMargin(TimeStampedModel):
    TYPE_CHOICES = CommissionRule.TYPE_CHOICES

    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    operator = models.ForeignKey(Operator, on_delete=models.CASCADE, null=True, blank=True)
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE)
    margin_value = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0.0000"))
    margin_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="percent")
    active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("service", "operator", "provider")]


class CommissionLedger(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="commission_ledger")
    transaction = models.ForeignKey(ServiceTransaction, on_delete=models.PROTECT, related_name="commission_entries")
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    entry_type = models.CharField(max_length=30, default="commission")
    remarks = models.CharField(max_length=240, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class EmailSetting(TimeStampedModel):
    provider_type = models.CharField(max_length=80, default="custom")
    host = models.CharField(max_length=160)
    port = models.PositiveIntegerField(default=587)
    username = models.CharField(max_length=160)
    encrypted_password = models.CharField(max_length=240)
    use_tls = models.BooleanField(default=True)
    use_ssl = models.BooleanField(default=False)
    from_email = models.EmailField()
    from_name = models.CharField(max_length=120, default="QuickZaps")
    active = models.BooleanField(default=True)
    last_test_status = models.CharField(max_length=120, blank=True)


class NewsItem(TimeStampedModel):
    title = models.CharField(max_length=160)
    body = models.TextField()
    target_role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True)
    active = models.BooleanField(default=True)
    priority = models.PositiveSmallIntegerField(default=5)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    dismissible = models.BooleanField(default=True)

    class Meta:
        ordering = ["priority", "-created_at"]


class PopupBanner(TimeStampedModel):
    SHOW_TYPE_CHOICES = [
        ("login", "Login"),
        ("dashboard", "Dashboard"),
        ("service", "Service Page"),
        ("mobile", "Mobile Only"),
        ("web", "Web Only"),
        ("all", "All"),
    ]

    title = models.CharField(max_length=160)
    image = models.ImageField(upload_to="popup_banners/", blank=True, null=True)
    show_type = models.CharField(max_length=20, choices=SHOW_TYPE_CHOICES, default="dashboard")
    active = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    display_frequency = models.CharField(max_length=40, default="once_per_login")


class BulkMessage(TimeStampedModel):
    CHANNEL_CHOICES = [("email", "Email"), ("whatsapp", "WhatsApp"), ("notification", "Notification")]
    STATUS_CHOICES = [("draft", "Draft"), ("sent", "Sent"), ("failed", "Failed")]

    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    target_role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True)
    subject = models.CharField(max_length=180, blank=True)
    body = models.TextField()
    attachment = models.FileField(upload_to="bulk_messages/", blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    sent_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="sent_bulk_messages")
    sent_at = models.DateTimeField(null=True, blank=True)
    recipient_count = models.PositiveIntegerField(default=0)


class Notification(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications", null=True, blank=True)
    target_role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField(max_length=160)
    body = models.TextField()
    attachment = models.FileField(upload_to="notifications/", blank=True, null=True)
    read_at = models.DateTimeField(null=True, blank=True)
    sent_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="sent_notifications")


class ProviderWebhookEvent(TimeStampedModel):
    provider = models.ForeignKey(Provider, on_delete=models.PROTECT)
    event_id = models.CharField(max_length=120)
    transaction_reference = models.CharField(max_length=80, blank=True)
    payload = models.JSONField(default=dict)
    processed_at = models.DateTimeField(null=True, blank=True)
    processing_status = models.CharField(max_length=40, default="received")

    class Meta:
        unique_together = [("provider", "event_id")]


class LoginHistory(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="login_history", null=True, blank=True)
    username = models.CharField(max_length=120)
    success = models.BooleanField(default=False)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    location = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["-created_at"]


class AuditLog(TimeStampedModel):
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs")
    action = models.CharField(max_length=120)
    entity_type = models.CharField(max_length=80)
    entity_id = models.CharField(max_length=80, blank=True)
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["actor", "created_at"]),
            models.Index(fields=["action", "entity_type"]),
        ]
