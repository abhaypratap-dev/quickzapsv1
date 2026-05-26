export type ID = number;

export type Paginated<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export type Role = {
  id: ID;
  code: string;
  name: string;
  level: number;
  permissions: string[];
  child_roles: ID[];
  child_role_codes: string[];
  active: boolean;
};

export type Wallet = {
  id: ID;
  user: ID;
  user_mobile?: string;
  user_name?: string;
  available_balance: string;
  hold_balance: string;
  cap_balance: string;
  total_balance?: string;
};

export type SecurityPolicy = {
  id: ID;
  user: ID;
  login_sms_otp_enabled: boolean;
  login_email_otp_enabled: boolean;
  login_whatsapp_otp_enabled: boolean;
  login_mpin_enabled: boolean;
  transaction_tpin_required: boolean;
  change_mpin_allowed: boolean;
  change_tpin_allowed: boolean;
  aadhaar_kyc_required: boolean;
  pan_kyc_required: boolean;
  cap_balance_enforced: boolean;
};

export type PartnerAPISetting = {
  id: ID;
  user: ID;
  user_mobile?: string;
  user_name?: string;
  api_key: string;
  allowed_ip?: string | null;
  allowed_ip2?: string | null;
  webhook_url: string;
  active: boolean;
  dummy_mode?: boolean;
  api_key_editable?: boolean;
  generated_at: string;
};

export type User = {
  id: ID;
  username: string;
  mobile: string;
  email: string;
  first_name: string;
  last_name: string;
  role: ID | null;
  role_name?: string;
  role_code?: string;
  parent: ID | null;
  parent_name?: string;
  parent_mobile?: string;
  status: "signup" | "active" | "inactive" | "deleted";
  kyc_status: "not_submitted" | "pending" | "approved" | "rejected" | "reupload_requested";
  scheme: ID | null;
  scheme_name?: string;
  service_package: ID | null;
  service_package_name?: string;
  cap_balance: string;
  company_name: string;
  business_type: string;
  address: string;
  city: string;
  state: string;
  pin_code: string;
  dob?: string | null;
  pan_number: string;
  aadhaar_number: string;
  wallet?: Wallet;
  security_policy?: SecurityPolicy;
  partner_api_setting?: PartnerAPISetting;
  last_login?: string | null;
  created_at?: string;
};

export type Service = {
  id: ID;
  code: string;
  name: string;
  category: string;
  active: boolean;
  requires_kyc: boolean;
  tpin_required: boolean;
  min_amount: string;
  max_amount: string;
};

export type Operator = {
  id: ID;
  service: ID;
  service_name?: string;
  code: string;
  name: string;
  active: boolean;
};

export type Provider = {
  id: ID;
  code: string;
  name: string;
  provider_type: string;
  base_url: string;
  active: boolean;
  health_status: "healthy" | "degraded" | "down";
  supports_webhook: boolean;
  supports_status_polling: boolean;
};

export type Scheme = {
  id: ID;
  role: ID;
  role_name?: string;
  role_code?: string;
  name: string;
  remark: string;
  active: boolean;
};

export type ServicePackage = {
  id: ID;
  name: string;
  description: string;
  active: boolean;
  slabs?: ServicePackageSlab[];
};

export type ServicePackageSlab = {
  id: ID;
  package: ID;
  service: ID;
  service_name?: string;
  service_amount: string;
};

export type Transaction = {
  id: ID;
  reference: string;
  initiated_by: ID;
  user_mobile?: string;
  user_name?: string;
  service: ID;
  service_name?: string;
  operator: ID | null;
  operator_name?: string;
  provider: ID | null;
  provider_name?: string;
  customer_mobile: string;
  amount: string;
  charge: string;
  commission: string;
  admin_margin: string;
  total_debit: string;
  status: "quoted" | "pending" | "success" | "failed" | "refunded" | "reversed" | "manual_review";
  provider_reference: string;
  description: string;
  created_at: string;
};

export type Quote = {
  service: Service;
  operator: Operator | null;
  provider: Provider;
  amount: string;
  charge: string;
  commission: string;
  gross_commission: string;
  tds: string;
  surcharge: string;
  gst: string;
  admin_margin: string;
  total_debit: string;
};

export type KYCProfile = {
  id: ID;
  user: ID;
  user_mobile?: string;
  user_name?: string;
  role_name?: string;
  status: User["kyc_status"];
  pan_number: string;
  aadhaar_number: string;
  aadhaar_front?: string | null;
  aadhaar_back?: string | null;
  pan_image?: string | null;
  shop_image?: string | null;
  user_photo?: string | null;
  rejection_reason: string;
  reviewed_at?: string | null;
};

export type AepsMerchantProfile = {
  id: ID;
  user: ID;
  user_mobile?: string;
  user_name?: string;
  merchant_login_id: string;
  merchant_phone_number: string;
  super_merchant_id: number;
  fingpay_merchant_status: boolean;
  status: "not_started" | "onboarding_pending" | "onboarded" | "active" | "rejected" | "suspended";
  kyc_status: "not_started" | "otp_sent" | "otp_validated" | "biometric_pending" | "verified" | "failed";
  can_access_services: boolean;
  next_step: "merchant_onboarding" | "ekyc" | "services";
  device_imei: string;
  latitude?: string | null;
  longitude?: string | null;
  merchant_state?: number | null;
  merchant_city_name: string;
  merchant_district_name: string;
  merchant_pin_code: string;
  company_legal_name: string;
  company_type?: number | null;
  company_bank_name: string;
  bank_ifsc_code: string;
  settlement_account_last4: string;
  bank_account_name: string;
  primary_key_id?: number | null;
  encode_fp_txn_id: string;
  last_provider_message: string;
  rejection_reason: string;
  last_onboarded_at?: string | null;
  last_ekyc_at?: string | null;
};

export type AepsPrefill = {
  merchant_login_id: string;
  merchant_phone_number: string;
  first_name: string;
  last_name: string;
  merchant_address1: string;
  merchant_address2: string;
  merchant_state: number;
  merchant_city_name: string;
  merchant_district_name: string;
  merchant_pin_code: string;
  company_legal_name: string;
  company_type: number;
  email_id: string;
  pan_number: string;
  aadhaar_masked: string;
  has_aadhaar: boolean;
  gstin_number: string;
  bank_account_number: string;
  bank_ifsc_code: string;
  company_bank_name: string;
  bank_account_name: string;
  device_imei: string;
  latitude: string;
  longitude: string;
};

export type AepsProfileState = {
  profile: AepsMerchantProfile | null;
  prefill: AepsPrefill;
  can_access_services: boolean;
  next_step: "merchant_onboarding" | "ekyc" | "services";
  dummy_mode: boolean;
  base_url: string;
  provider_response?: Record<string, unknown>;
};

export type OnboardingRole = "SDBR" | "DBR" | "RETAILER";
export type OnboardingStatus = "draft" | "pending_parent" | "pending_admin" | "approved" | "rejected" | "created";

export type OnboardingParent = {
  id: ID;
  mobile: string;
  name: string;
  role_name: string;
  role_code: string;
};

export type OnboardingApplication = {
  id: ID;
  requested_role: OnboardingRole;
  requested_role_label?: string;
  status: OnboardingStatus;
  submitted_by?: ID | null;
  submitted_by_name?: string;
  agent?: ID | null;
  agent_name?: string;
  parent?: ID | null;
  parent_name?: string;
  parent_mobile?: string;
  parent_role_name?: string;
  approved_by_name?: string;
  created_user?: ID | null;
  created_user_mobile?: string;
  direct_to_admin: boolean;
  mobile: string;
  email: string;
  full_name: string;
  dob: string;
  aadhaar_number: string;
  pan_number: string;
  verification_mode: string;
  pan_verification: Record<string, unknown>;
  aadhaar_verification: Record<string, unknown>;
  bank_verification: Record<string, unknown>;
  gst_verification: Record<string, unknown>;
  udyam_verification: Record<string, unknown>;
  live_photo?: string | null;
  live_photo_geo: Record<string, unknown>;
  shop_photo?: string | null;
  shop_photo_geo: Record<string, unknown>;
  agent_photo?: string | null;
  agent_photo_geo: Record<string, unknown>;
  account_holder_name: string;
  bank_name: string;
  account_number: string;
  ifsc: string;
  upi_id: string;
  bank_proof?: string | null;
  rpd_reference_id: string;
  rpd_link: string;
  rpd_status: string;
  business_name: string;
  business_type: string;
  gst_number: string;
  udyam_number: string;
  business_address: string;
  city: string;
  state: string;
  pin_code: string;
  business_photo?: string | null;
  gst_document?: string | null;
  udyam_document?: string | null;
  review_note: string;
  approved_at?: string | null;
  rejected_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type FundRequest = {
  id: ID;
  user: ID;
  user_mobile?: string;
  user_name?: string;
  amount: string;
  method: "bank" | "upi" | "cash" | "gateway";
  payment_reference: string;
  status: "pending" | "approved" | "rejected";
  note: string;
  review_note: string;
  created_at: string;
};

export type PaymentGatewayOrder = {
  id: ID;
  user: ID;
  user_mobile?: string;
  reference: string;
  amount: string;
  status: "created" | "success" | "failed";
  provider_reference: string;
  payment_link?: string;
  payment_link_id?: string;
  provider_name?: string;
  sandbox_mode?: boolean;
  created_at: string;
};

export type LedgerEntry = {
  id: ID;
  user: ID;
  user_mobile?: string;
  user_name?: string;
  entry_type: string;
  amount: string;
  opening_balance: string;
  closing_balance: string;
  transaction_ref: string;
  remarks: string;
  service_name?: string;
  created_at: string;
};

export type CommissionLedger = {
  id: ID;
  user: ID;
  user_mobile?: string;
  user_name?: string;
  transaction_reference?: string;
  service_name?: string;
  amount: string;
  entry_type: string;
  remarks: string;
  created_at: string;
};

export type Dashboard = {
  totals: Record<string, number | string | null>;
  service_summary: Array<Record<string, string | number | null>>;
  trend: Array<Record<string, string | number | null>>;
  last_transactions: Transaction[];
  wallet_totals: Record<string, string | null>;
  pending_counts: Record<string, number>;
  news: NewsItem[];
};

export type NewsItem = {
  id: ID;
  title: string;
  body: string;
  target_role: ID | null;
  target_role_name?: string;
  active: boolean;
  priority: number;
};

export type PopupBanner = {
  id: ID;
  title: string;
  show_type: string;
  active: boolean;
  description: string;
  image?: string | null;
};

export type BulkMessage = {
  id: ID;
  channel: "email" | "whatsapp" | "notification";
  target_role: ID | null;
  target_role_name?: string;
  subject: string;
  body: string;
  status: "draft" | "sent" | "failed";
  recipient_count: number;
  created_at: string;
};

export type CommissionRule = {
  id: ID;
  scheme: ID;
  scheme_name?: string;
  service: ID;
  service_name?: string;
  operator: ID | null;
  operator_name?: string;
  commission_value: string;
  commission_type: "fixed" | "percent";
  surcharge_value: string;
  surcharge_type: "fixed" | "percent";
  tds_percent: string;
  gst_percent: string;
  active: boolean;
};

export type ApiMargin = {
  id: ID;
  service: ID;
  service_name?: string;
  operator: ID | null;
  operator_name?: string;
  provider: ID;
  provider_name?: string;
  margin_value: string;
  margin_type: "fixed" | "percent";
  active: boolean;
};

// ─── Partner API Response wrapper ────────────────────────────────────────────
export type PartnerAPIResponse<T = unknown> = {
  StatusCode: string;
  Message: string;
  data: T;
};

// ─── Payout result ────────────────────────────────────────────────────────────
export type PayoutResult = {
  OrderID: string;
  Tid: string;
  Amount: string | number;
  TxStatus: string;
  AccounNumber: string;
  AccountHolderName: string;
  IfscCode: string;
  TransactionaDate: string;
  Utr: string;
};

// ─── BBPS bill fetch result ───────────────────────────────────────────────────
export type BBPSBillFetchResult = {
  reference_id: string;
  consumer_number: string;
  customer_name: string;
  bill_amount: string | number;
  due_date: string;
  status: string;
};

// ─── CMS session result ───────────────────────────────────────────────────────
export type CMSResult = {
  transaction_id: string;
  mobile_number: string;
  status: string;
  redirect_url: string;
};
