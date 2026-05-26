import { Platform } from "react-native";

import type {
  AepsProfileState,
  ApiMargin,
  BBPSBillFetchResult,
  BulkMessage,
  CMSResult,
  CommissionLedger,
  CommissionRule,
  Dashboard,
  FundRequest,
  ID,
  KYCProfile,
  LedgerEntry,
  NewsItem,
  OnboardingApplication,
  OnboardingParent,
  Operator,
  Paginated,
  PartnerAPIResponse,
  PartnerAPISetting,
  PaymentGatewayOrder,
  PayoutResult,
  PopupBanner,
  Provider,
  Quote,
  Role,
  Scheme,
  Service,
  ServicePackage,
  Transaction,
  User,
  Wallet
} from "@/types";

const rawBaseUrl = process.env.EXPO_PUBLIC_API_URL || "http://127.0.0.1:8000/api";
export const API_BASE_URL = rawBaseUrl.replace(/\/$/, "");

let accessToken: string | null = null;
let refreshToken: string | null = null;

export function setApiTokens(tokens: { access?: string | null; refresh?: string | null }) {
  accessToken = tokens.access ?? null;
  refreshToken = tokens.refresh ?? null;
}

export function getApiTokens() {
  return { access: accessToken, refresh: refreshToken };
}

type RequestOptions = RequestInit & {
  auth?: boolean;
  formData?: boolean;
};

export class ApiError extends Error {
  status: number;
  details: unknown;

  constructor(status: number, message: string, details: unknown) {
    super(message);
    this.status = status;
    this.details = details;
  }
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (!options.formData) {
    headers.set("Content-Type", "application/json");
  }
  if (options.auth !== false && accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers
  });

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json") ? await response.json() : await response.text();

  if (!response.ok) {
    const message =
      typeof body === "object" && body && "error" in body
        ? ((body as { error?: { message?: string } }).error?.message ?? "Request failed")
        : typeof body === "object"
          ? JSON.stringify(body)
          : String(body || "Request failed");
    throw new ApiError(response.status, message, body);
  }
  return body as T;
}

function params(query?: Record<string, string | number | boolean | null | undefined>) {
  const search = new URLSearchParams();
  Object.entries(query || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  });
  const value = search.toString();
  return value ? `?${value}` : "";
}

function endpoint(path: string, query?: Record<string, string | number | boolean | null | undefined>) {
  return `${path}${params(query)}`;
}

function body(data: unknown) {
  return JSON.stringify(data);
}

function normalizeList<T>(payload: Paginated<T> | T[]): T[] {
  return Array.isArray(payload) ? payload : payload.results;
}

// ─── Partner API helper ───────────────────────────────────────────────────────
// Sends POST to a partner-style endpoint with API-key headers.
// In PARTNER_API_DUMMY_MODE the backend skips signature validation,
// so we can use placeholder values for x-signature.
const PARTNER_API_DUMMY_KEY = "quickzaps-dummy-key";

async function partnerRequest<T>(path: string, data: Record<string, unknown>): Promise<PartnerAPIResponse<T>> {
  const timestamp = Math.floor(Date.now() / 1000).toString();
  const requestId = `UI-${Date.now()}-${Math.random().toString(36).slice(2, 8).toUpperCase()}`;
  const headers = new Headers({
    "Content-Type": "application/json",
    "x-api-key": PARTNER_API_DUMMY_KEY,
    "x-timestamp": timestamp,
    "x-request-id": requestId,
    "x-signature": "0".repeat(64),
  });

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(data),
  });

  let responseBody: PartnerAPIResponse<T>;
  try {
    responseBody = await response.json();
  } catch {
    throw new ApiError(response.status, "Partner API returned an invalid response.", null);
  }

  if (!response.ok || (responseBody.StatusCode && responseBody.StatusCode !== "200" && responseBody.StatusCode !== "201")) {
    throw new ApiError(response.status || 400, responseBody?.Message || "Partner API request failed.", responseBody);
  }

  return responseBody;
}

export const api = {
  async login(username: string, password: string) {
    return request<{ access: string; refresh: string; user: User }>("/auth/login/", {
      auth: false,
      method: "POST",
      body: body({ username, password })
    });
  },
  async me() {
    return request<User>("/auth/me/");
  },
  async refresh() {
    if (!refreshToken) {
      throw new ApiError(401, "No refresh token is available.", null);
    }
    return request<{ access: string }>("/auth/refresh/", {
      auth: false,
      method: "POST",
      body: body({ refresh: refreshToken })
    });
  },
  async roles(query?: Record<string, string | number | boolean>) {
    return normalizeList(await request<Paginated<Role> | Role[]>(endpoint("/roles/", query)));
  },
  async users(query?: Record<string, string | number | boolean>) {
    return normalizeList(await request<Paginated<User> | User[]>(endpoint("/users/", query)));
  },
  async createUser(data: Record<string, unknown>) {
    return request<User>("/users/", { method: "POST", body: body(data) });
  },
  async updateUser(id: ID, data: Record<string, unknown>) {
    return request<User>(`/users/${id}/`, { method: "PATCH", body: body(data) });
  },
  async setUserStatus(id: ID, status: User["status"]) {
    return request<User>(`/users/${id}/set-status/`, { method: "POST", body: body({ status }) });
  },
  async restoreUser(id: ID) {
    return request<User>(`/users/${id}/restore/`, { method: "POST", body: body({}) });
  },
  async upgradeUser(data: { user: ID; new_role: ID; scheme?: ID | null }) {
    return request<User>("/users/upgrade/", { method: "POST", body: body(data) });
  },
  async updateSecurityPolicy(id: ID, data: Record<string, boolean>) {
    return request(`/users/${id}/security-policy/`, { method: "PATCH", body: body(data) });
  },
  async partnerApiSettings(query?: Record<string, string | number | boolean>) {
    return normalizeList(await request<Paginated<PartnerAPISetting> | PartnerAPISetting[]>(endpoint("/partner-api-settings/", query)));
  },
  async partnerApiMine() {
    return request<PartnerAPISetting>("/partner-api-settings/mine/");
  },
  async updatePartnerApiMine(data: Partial<Pick<PartnerAPISetting, "api_key" | "allowed_ip" | "allowed_ip2" | "webhook_url" | "active">>) {
    return request<PartnerAPISetting>("/partner-api-settings/mine/", { method: "PATCH", body: body(data) });
  },
  async rotatePartnerApiKey() {
    return request<PartnerAPISetting>("/partner-api-settings/rotate/", { method: "POST", body: body({}) });
  },
  async services(query?: Record<string, string | number | boolean>) {
    return normalizeList(await request<Paginated<Service> | Service[]>(endpoint("/services/", query)));
  },
  async operators(query?: Record<string, string | number | boolean>) {
    return normalizeList(await request<Paginated<Operator> | Operator[]>(endpoint("/operators/", query)));
  },
  async providers(query?: Record<string, string | number | boolean>) {
    return normalizeList(await request<Paginated<Provider> | Provider[]>(endpoint("/providers/", query)));
  },
  async schemes(query?: Record<string, string | number | boolean>) {
    return normalizeList(await request<Paginated<Scheme> | Scheme[]>(endpoint("/schemes/", query)));
  },
  async createScheme(data: Record<string, unknown>) {
    return request<Scheme>("/schemes/", { method: "POST", body: body(data) });
  },
  async servicePackages(query?: Record<string, string | number | boolean>) {
    return normalizeList(await request<Paginated<ServicePackage> | ServicePackage[]>(endpoint("/service-packages/", query)));
  },
  async createServicePackage(data: Record<string, unknown>) {
    return request<ServicePackage>("/service-packages/", { method: "POST", body: body(data) });
  },
  async createPackageSlab(data: Record<string, unknown>) {
    return request("/service-package-slabs/", { method: "POST", body: body(data) });
  },
  async commissionRules(query?: Record<string, string | number | boolean>) {
    return normalizeList(await request<Paginated<CommissionRule> | CommissionRule[]>(endpoint("/commission-rules/", query)));
  },
  async saveCommissionRule(data: Record<string, unknown>, id?: ID) {
    return request<CommissionRule>(id ? `/commission-rules/${id}/` : "/commission-rules/", {
      method: id ? "PATCH" : "POST",
      body: body(data)
    });
  },
  async apiMargins(query?: Record<string, string | number | boolean>) {
    return normalizeList(await request<Paginated<ApiMargin> | ApiMargin[]>(endpoint("/api-margins/", query)));
  },
  async saveApiMargin(data: Record<string, unknown>, id?: ID) {
    return request<ApiMargin>(id ? `/api-margins/${id}/` : "/api-margins/", {
      method: id ? "PATCH" : "POST",
      body: body(data)
    });
  },
  async dashboard() {
    return request<Dashboard>("/reports/dashboard/");
  },
  async transactions(query?: Record<string, string | number | boolean>) {
    return normalizeList(await request<Paginated<Transaction> | Transaction[]>(endpoint("/transactions/", query)));
  },
  async quote(data: Record<string, unknown>) {
    return request<Quote>("/transactions/quote/", { method: "POST", body: body(data) });
  },
  async executeTransaction(data: Record<string, unknown>) {
    return request<Transaction>("/transactions/execute/", { method: "POST", body: body(data) });
  },
  async reverseTransaction(id: ID, reason: string) {
    return request<Transaction>(`/transactions/${id}/reverse/`, { method: "POST", body: body({ reason }) });
  },
  async walletMine() {
    return request<Wallet>("/wallets/mine/");
  },
  async wallets(query?: Record<string, string | number | boolean>) {
    return normalizeList(await request<Paginated<Wallet> | Wallet[]>(endpoint("/wallets/", query)));
  },
  async ledger(query?: Record<string, string | number | boolean>) {
    return normalizeList(await request<Paginated<LedgerEntry> | LedgerEntry[]>(endpoint("/wallets/ledger/", query)));
  },
  async adjustWallet(data: Record<string, unknown>) {
    return request<Wallet>("/wallets/adjust/", { method: "POST", body: body(data) });
  },
  async fundRequests(query?: Record<string, string | number | boolean>) {
    return normalizeList(await request<Paginated<FundRequest> | FundRequest[]>(endpoint("/fund-requests/", query)));
  },
  async createFundRequest(data: Record<string, unknown>) {
    return request<FundRequest>("/fund-requests/", { method: "POST", body: body(data) });
  },
  async reviewFundRequest(id: ID, data: { status: "approved" | "rejected"; review_note?: string }) {
    return request<FundRequest>(`/fund-requests/${id}/review/`, { method: "POST", body: body(data) });
  },
  async createGatewayOrder(amount: string) {
    return request<PaymentGatewayOrder>("/gateway-orders/", { method: "POST", body: body({ amount }) });
  },
  async completeGatewayOrder(id: ID, status: "success" | "failed" = "success") {
    return request<PaymentGatewayOrder>(`/gateway-orders/${id}/complete/`, {
      method: "POST",
      body: body({ status })
    });
  },
  async kyc(query?: Record<string, string | number | boolean>) {
    return normalizeList(await request<Paginated<KYCProfile> | KYCProfile[]>(endpoint("/kyc/", query)));
  },
  async myKyc() {
    return request<KYCProfile>("/kyc/mine/");
  },
  async submitKyc(data: FormData | Record<string, unknown>) {
    if (data instanceof FormData) {
      return request<KYCProfile>("/kyc/submit/", {
        method: "POST",
        body: data,
        formData: true
      });
    }
    return request<KYCProfile>("/kyc/submit/", { method: "POST", body: body(data) });
  },
  async reviewKyc(id: ID, data: { status: KYCProfile["status"]; reason?: string }) {
    return request<KYCProfile>(`/kyc/${id}/review/`, { method: "POST", body: body(data) });
  },
  async aepsProfile() {
    return request<AepsProfileState>("/aeps/profile/");
  },
  async onboardAepsMerchant(data: Record<string, unknown>) {
    return request<AepsProfileState>("/aeps/onboard/", { method: "POST", body: body(data) });
  },
  async sendAepsKycOtp(data: Record<string, unknown>) {
    return request<AepsProfileState>("/aeps/kyc/send-otp/", { method: "POST", body: body(data) });
  },
  async validateAepsKycOtp(data: Record<string, unknown>) {
    return request<AepsProfileState>("/aeps/kyc/validate-otp/", { method: "POST", body: body(data) });
  },
  async aepsBiometricKyc(data: Record<string, unknown>) {
    return request<AepsProfileState>("/aeps/kyc/biometric/", { method: "POST", body: body(data) });
  },
  async refreshAepsKycStatus() {
    return request<AepsProfileState>("/aeps/kyc/status/", { method: "POST", body: body({}) });
  },
  async aepsBanks() {
    return request<Record<string, unknown>>("/aeps/banks/");
  },
  async executeAepsTransaction(data: Record<string, unknown>) {
    return request<{ transaction: Transaction; provider_response: Record<string, unknown>; profile: AepsProfileState["profile"] }>("/aeps/transactions/execute/", {
      method: "POST",
      body: body(data)
    });
  },
  async onboardingApplications(query?: Record<string, string | number | boolean>) {
    return normalizeList(await request<Paginated<OnboardingApplication> | OnboardingApplication[]>(endpoint("/onboarding-applications/", query)));
  },
  async onboardingParents(requestedRole: string) {
    return request<OnboardingParent[]>(endpoint("/onboarding-applications/parents/", { requested_role: requestedRole }));
  },
  async verifyOnboardingIdentity(data: Record<string, unknown>) {
    return request<Record<string, unknown>>("/onboarding-applications/verify-identity/", { method: "POST", body: body(data) });
  },
  async digilockerInit(redirectUrl?: string) {
    return request<Record<string, unknown>>("/onboarding-applications/digilocker-init/", { method: "POST", body: body({ redirect_url: redirectUrl || "" }) });
  },
  async digilockerStatus(verificationId: string) {
    return request<Record<string, unknown>>(`/onboarding-applications/digilocker-status/?verification_id=${encodeURIComponent(verificationId)}`);
  },
  async digilockerDocument(verificationId: string) {
    return request<Record<string, unknown>>(`/onboarding-applications/digilocker-document/?verification_id=${encodeURIComponent(verificationId)}`);
  },
  async verifyOnboardingBank(data: Record<string, unknown>) {
    return request<Record<string, unknown>>("/onboarding-applications/verify-bank/", { method: "POST", body: body(data) });
  },
  async verifyOnboardingBusiness(data: Record<string, unknown>) {
    return request<Record<string, unknown>>("/onboarding-applications/verify-business/", { method: "POST", body: body(data) });
  },
  async submitOnboarding(data: FormData) {
    return request<OnboardingApplication>("/onboarding-applications/", {
      method: "POST",
      body: data,
      formData: true
    });
  },
  async reviewOnboarding(id: ID, data: { action: "approve" | "reject"; note?: string }) {
    return request<OnboardingApplication>(`/onboarding-applications/${id}/review/`, { method: "POST", body: body(data) });
  },
  async news(query?: Record<string, string | number | boolean>) {
    return normalizeList(await request<Paginated<NewsItem> | NewsItem[]>(endpoint("/news/", query)));
  },
  async createNews(data: Record<string, unknown>) {
    return request<NewsItem>("/news/", { method: "POST", body: body(data) });
  },
  async popupBanners(query?: Record<string, string | number | boolean>) {
    return normalizeList(await request<Paginated<PopupBanner> | PopupBanner[]>(endpoint("/popup-banners/", query)));
  },
  async createPopupBanner(data: Record<string, unknown>) {
    return request<PopupBanner>("/popup-banners/", { method: "POST", body: body(data) });
  },
  async bulkMessages(query?: Record<string, string | number | boolean>) {
    return normalizeList(await request<Paginated<BulkMessage> | BulkMessage[]>(endpoint("/bulk-messages/", query)));
  },
  async createBulkMessage(data: Record<string, unknown>) {
    return request<BulkMessage>("/bulk-messages/", { method: "POST", body: body(data) });
  },
  async sendBulkMessage(id: ID) {
    return request<BulkMessage>(`/bulk-messages/${id}/send/`, { method: "POST", body: body({}) });
  },
  async commissionLedger() {
    return request<CommissionLedger[]>("/reports/commission-ledger/");
  },
  async walletSummary() {
    return request<Wallet[]>("/reports/wallet-summary/");
  },
  async reportLedger() {
    return request<LedgerEntry[]>("/reports/ledger/");
  },
  async dayBook() {
    return request("/reports/day-book/");
  },

  // ─── Partner API methods (mock-compatible, dummy mode bypasses signature) ───
  async initiatePayout(data: {
    OrderId: string;
    PayoutPipe: string;
    Amount: string | number;
    BeneficiaryName: string;
    AccountNumber: string;
    Ifsc: string;
    BankName: string;
    TransferMode: string;
    AccountType: string;
    MobileNumber: string;
    Remarks: string;
  }): Promise<PartnerAPIResponse<PayoutResult>> {
    return partnerRequest<PayoutResult>("/PayoutApi/Payoutinitiate/", data as Record<string, unknown>);
  },

  async createPayinLink(data: {
    OrderId: string;
    PayinType: string;
    Amount: string | number;
    BeneficiaryName: string;
    MobileNumber: string;
    EmailID: string;
  }): Promise<PartnerAPIResponse<Record<string, unknown>>> {
    return partnerRequest<Record<string, unknown>>("/PayinApi/CreatePaymentLink/", data as Record<string, unknown>);
  },

  async initiateRecharge(data: {
    OrderId: string;
    ServiceType: string;
    OperatorCode: string;
    MobileNumber: string;
    Amount: string | number;
    Circle: string;
  }): Promise<PartnerAPIResponse<Transaction>> {
    return partnerRequest<Transaction>("/RechargeApi/Rechargeinitiate/", data as Record<string, unknown>);
  },

  async bbpsFetchBill(data: {
    ServiceType: string;
    OperatorCode: string;
    ConsumerNo: string;
    MobileNumber: string;
    EmailId: string;
    Dob?: string;
    Amount?: string;
  }): Promise<PartnerAPIResponse<BBPSBillFetchResult>> {
    return partnerRequest<BBPSBillFetchResult>("/BBPSApi/FetchBill/", data as Record<string, unknown>);
  },

  async bbpsPayBill(data: {
    OrderId: string;
    ServiceType: string;
    OperatorCode: string;
    Amount: string | number;
    ConsumerNo: string;
    ConsumerName: string;
    ReferenceId: string;
    MobileNumber: string;
    EmailId?: string;
    Latitude?: string;
    Longitude?: string;
  }): Promise<PartnerAPIResponse<Transaction>> {
    return partnerRequest<Transaction>("/BBPSApi/PayBill/", data as Record<string, unknown>);
  },

  async initiateCMS(data: {
    MobileNumber: string;
    OrderId: string;
  }): Promise<PartnerAPIResponse<CMSResult>> {
    return partnerRequest<CMSResult>("/CMSApi/Initiate/", data as Record<string, unknown>);
  },

  async partnerTransactionStatus(data: {
    OrderId: string;
  }): Promise<PartnerAPIResponse<Transaction>> {
    return partnerRequest<Transaction>("/TransactionApi/Status/", data as Record<string, unknown>);
  }
};

export function canUseFileUploads() {
  return Platform.OS !== "web" || typeof FormData !== "undefined";
}
