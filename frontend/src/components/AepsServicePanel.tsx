import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import React, { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { api } from "@/api/client";
import { Button, DataTable, ErrorText, Field, Grid, Panel, SelectBox, StatusBadge } from "@/components/ui";
import { useTheme } from "@/context/ThemeContext";
import type { AepsProfileState, Transaction } from "@/types";
import { dateTime, money } from "@/utils/format";

function parseJsonObject(value: string) {
  try {
    const parsed = JSON.parse(value || "{}");
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? (parsed as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

function jsonPreview(value?: Record<string, unknown> | null) {
  return value ? JSON.stringify(value, null, 2) : "";
}

function useAepsStateMutation(mutationFn: () => Promise<AepsProfileState>, setError: (message: string) => void) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: (response) => {
      queryClient.setQueryData(["aeps-profile"], response);
      setError("");
    },
    onError: (err) => setError(err instanceof Error ? err.message : "AEPS request failed."),
  });
}

function AepsStatusPanel({ state }: { state: AepsProfileState }) {
  const { colors } = useTheme();
  const profile = state.profile;
  return (
    <View style={[styles.statusRow, { backgroundColor: colors.panelAlt, borderColor: colors.line }]}>
      <View style={styles.statusItem}>
        <Text style={[styles.statusLabel, { color: colors.muted }]}>Merchant</Text>
        <Text selectable style={[styles.statusValue, { color: colors.ink }]}>
          {profile?.merchant_login_id || state.prefill.merchant_login_id}
        </Text>
      </View>
      <View style={styles.statusItem}>
        <Text style={[styles.statusLabel, { color: colors.muted }]}>Onboarding</Text>
        <StatusBadge status={profile?.status ?? "not_started"} />
      </View>
      <View style={styles.statusItem}>
        <Text style={[styles.statusLabel, { color: colors.muted }]}>KYC</Text>
        <StatusBadge status={profile?.kyc_status ?? "not_started"} />
      </View>
      <View style={styles.statusItem}>
        <Text style={[styles.statusLabel, { color: colors.muted }]}>Mode</Text>
        <Text style={[styles.statusValue, { color: colors.ink }]}>{state.dummy_mode ? "Fingpay dummy" : "Fingpay live"}</Text>
      </View>
    </View>
  );
}

function AepsOnboardingForm({ state }: { state: AepsProfileState }) {
  const queryClient = useQueryClient();
  const { colors } = useTheme();
  const [form, setForm] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [providerResponse, setProviderResponse] = useState<Record<string, unknown> | undefined>(state.provider_response);

  useEffect(() => {
    const p = state.prefill;
    setForm({
      merchant_login_id: p.merchant_login_id || "",
      merchant_pin: "",
      first_name: p.first_name || "",
      last_name: p.last_name || "",
      merchant_phone_number: p.merchant_phone_number || "",
      merchant_address1: p.merchant_address1 || "",
      merchant_address2: p.merchant_address2 || "",
      merchant_state: String(p.merchant_state || ""),
      merchant_city_name: p.merchant_city_name || "",
      merchant_district_name: p.merchant_district_name || "",
      merchant_pin_code: p.merchant_pin_code || "",
      company_legal_name: p.company_legal_name || "",
      company_type: String(p.company_type || ""),
      email_id: p.email_id || "",
      pan_number: p.pan_number || "",
      aadhaar_number: "",
      gstin_number: p.gstin_number || "",
      bank_account_number: p.bank_account_number || "",
      bank_ifsc_code: p.bank_ifsc_code || "",
      company_bank_name: p.company_bank_name || "",
      bank_account_name: p.bank_account_name || "",
      device_imei: p.device_imei || "",
      latitude: p.latitude || "",
      longitude: p.longitude || "",
    });
  }, [state.prefill]);

  const setField = (key: string, value: string) => setForm((current) => ({ ...current, [key]: value }));

  const mutation = useMutation({
    mutationFn: () =>
      api.onboardAepsMerchant({
        ...form,
        merchant_state: Number(form.merchant_state),
        company_type: Number(form.company_type),
        latitude: form.latitude || undefined,
        longitude: form.longitude || undefined,
      }),
    onSuccess: (nextState) => {
      queryClient.setQueryData(["aeps-profile"], nextState);
      setProviderResponse(nextState.provider_response);
      setError("");
    },
    onError: (err) => setError(err instanceof Error ? err.message : "AEPS merchant onboarding failed."),
  });

  const required = [
    "merchant_login_id",
    "merchant_pin",
    "first_name",
    "last_name",
    "merchant_phone_number",
    "merchant_address1",
    "merchant_address2",
    "merchant_state",
    "merchant_city_name",
    "merchant_district_name",
    "merchant_pin_code",
    "company_legal_name",
    "company_type",
    "pan_number",
    "bank_account_number",
    "bank_ifsc_code",
    "company_bank_name",
    "bank_account_name",
  ];
  const canSubmit = required.every((key) => String(form[key] || "").trim()) && !mutation.isPending;

  return (
    <Panel title="AEPS Merchant Onboarding">
      <AepsStatusPanel state={state} />
      {state.prefill.aadhaar_masked ? (
        <Text style={{ color: colors.muted, fontWeight: "700" }}>Aadhaar on file: {state.prefill.aadhaar_masked}</Text>
      ) : null}
      <Grid>
        <Field label="Merchant Login ID" value={form.merchant_login_id || ""} onChangeText={(v) => setField("merchant_login_id", v)} />
        <Field label="Merchant PIN" value={form.merchant_pin || ""} onChangeText={(v) => setField("merchant_pin", v)} keyboardType="numeric" secureTextEntry />
        <Field label="First Name" value={form.first_name || ""} onChangeText={(v) => setField("first_name", v)} />
        <Field label="Last Name" value={form.last_name || ""} onChangeText={(v) => setField("last_name", v)} />
        <Field label="Mobile Number" value={form.merchant_phone_number || ""} onChangeText={(v) => setField("merchant_phone_number", v)} keyboardType="phone-pad" />
        <Field label="Email ID" value={form.email_id || ""} onChangeText={(v) => setField("email_id", v)} keyboardType="email-address" />
        <Field label="PAN Number" value={form.pan_number || ""} onChangeText={(v) => setField("pan_number", v.toUpperCase())} />
        <Field label="Aadhaar Number" value={form.aadhaar_number || ""} onChangeText={(v) => setField("aadhaar_number", v)} keyboardType="numeric" placeholder={state.prefill.aadhaar_masked || "12 digit Aadhaar"} />
        <Field label="Address Line 1" value={form.merchant_address1 || ""} onChangeText={(v) => setField("merchant_address1", v)} />
        <Field label="Address Line 2" value={form.merchant_address2 || ""} onChangeText={(v) => setField("merchant_address2", v)} />
        <Field label="Fingpay State Code" value={form.merchant_state || ""} onChangeText={(v) => setField("merchant_state", v)} keyboardType="numeric" />
        <Field label="City" value={form.merchant_city_name || ""} onChangeText={(v) => setField("merchant_city_name", v)} />
        <Field label="District" value={form.merchant_district_name || ""} onChangeText={(v) => setField("merchant_district_name", v)} />
        <Field label="PIN Code" value={form.merchant_pin_code || ""} onChangeText={(v) => setField("merchant_pin_code", v)} keyboardType="numeric" />
        <Field label="Company Legal Name" value={form.company_legal_name || ""} onChangeText={(v) => setField("company_legal_name", v)} />
        <Field label="Company Type" value={form.company_type || ""} onChangeText={(v) => setField("company_type", v)} keyboardType="numeric" />
        <Field label="GSTIN" value={form.gstin_number || ""} onChangeText={(v) => setField("gstin_number", v.toUpperCase())} />
        <Field label="Bank Account Number" value={form.bank_account_number || ""} onChangeText={(v) => setField("bank_account_number", v)} keyboardType="numeric" />
        <Field label="IFSC Code" value={form.bank_ifsc_code || ""} onChangeText={(v) => setField("bank_ifsc_code", v.toUpperCase())} />
        <Field label="Bank Name" value={form.company_bank_name || ""} onChangeText={(v) => setField("company_bank_name", v)} />
        <Field label="Account Holder Name" value={form.bank_account_name || ""} onChangeText={(v) => setField("bank_account_name", v)} />
        <Field label="Device IMEI / Serial" value={form.device_imei || ""} onChangeText={(v) => setField("device_imei", v)} />
        <Field label="Latitude" value={form.latitude || ""} onChangeText={(v) => setField("latitude", v)} keyboardType="numeric" />
        <Field label="Longitude" value={form.longitude || ""} onChangeText={(v) => setField("longitude", v)} keyboardType="numeric" />
      </Grid>
      <ErrorText message={error} />
      <Button icon="account-check-outline" onPress={() => mutation.mutate()} disabled={!canSubmit}>
        {mutation.isPending ? "Submitting..." : "Submit Merchant Onboarding"}
      </Button>
      {providerResponse ? (
        <Text selectable style={[styles.providerJson, { color: colors.muted, backgroundColor: colors.panelAlt }]}>
          {jsonPreview(providerResponse)}
        </Text>
      ) : null}
    </Panel>
  );
}

function AepsKycPanel({ state }: { state: AepsProfileState }) {
  const { colors } = useTheme();
  const [aadhaarNumber, setAadhaarNumber] = useState("");
  const [panNumber, setPanNumber] = useState(state.prefill.pan_number || "");
  const [mobileNumber, setMobileNumber] = useState(state.prefill.merchant_phone_number || "");
  const [deviceImei, setDeviceImei] = useState(state.profile?.device_imei || state.prefill.device_imei || "");
  const [latitude, setLatitude] = useState(String(state.profile?.latitude ?? state.prefill.latitude ?? ""));
  const [longitude, setLongitude] = useState(String(state.profile?.longitude ?? state.prefill.longitude ?? ""));
  const [otp, setOtp] = useState("");
  const [captureResponse, setCaptureResponse] = useState("{}");
  const [error, setError] = useState("");
  const [providerResponse, setProviderResponse] = useState<Record<string, unknown> | undefined>(state.provider_response);

  const sendOtpMutation = useAepsStateMutation(
    () =>
      api.sendAepsKycOtp({
        aadhaar_number: aadhaarNumber,
        pan_number: panNumber,
        mobile_number: mobileNumber,
        device_imei: deviceImei,
        latitude: latitude || undefined,
        longitude: longitude || undefined,
      }),
    setError,
  );
  const validateOtpMutation = useAepsStateMutation(() => api.validateAepsKycOtp({ otp, device_imei: deviceImei }), setError);
  const statusMutation = useAepsStateMutation(() => api.refreshAepsKycStatus(), setError);
  const biometricMutation = useAepsStateMutation(() => {
    const parsed = parseJsonObject(captureResponse);
    if (!parsed) throw new Error("Capture Response must be valid JSON.");
    return api.aepsBiometricKyc({
      aadhaar_number: aadhaarNumber,
      bank_iin: "",
      capture_response: parsed,
      device_imei: deviceImei,
    });
  }, setError);

  useEffect(() => {
    const latest = sendOtpMutation.data ?? validateOtpMutation.data ?? statusMutation.data ?? biometricMutation.data;
    if (latest?.provider_response) setProviderResponse(latest.provider_response);
  }, [biometricMutation.data, sendOtpMutation.data, statusMutation.data, validateOtpMutation.data]);

  return (
    <Panel title="AEPS Merchant KYC">
      <AepsStatusPanel state={state} />
      {state.prefill.aadhaar_masked ? (
        <Text style={{ color: colors.muted, fontWeight: "700" }}>Aadhaar on file: {state.prefill.aadhaar_masked}</Text>
      ) : null}
      <Grid>
        <Field label="Aadhaar Number" value={aadhaarNumber} onChangeText={setAadhaarNumber} keyboardType="numeric" placeholder={state.prefill.aadhaar_masked || "12 digit Aadhaar"} />
        <Field label="PAN Number" value={panNumber} onChangeText={(v) => setPanNumber(v.toUpperCase())} />
        <Field label="Mobile Number" value={mobileNumber} onChangeText={setMobileNumber} keyboardType="phone-pad" />
        <Field label="Device IMEI / Serial" value={deviceImei} onChangeText={setDeviceImei} />
        <Field label="Latitude" value={latitude} onChangeText={setLatitude} keyboardType="numeric" />
        <Field label="Longitude" value={longitude} onChangeText={setLongitude} keyboardType="numeric" />
      </Grid>
      <Grid>
        <Button icon="message-processing-outline" onPress={() => sendOtpMutation.mutate()} disabled={sendOtpMutation.isPending || (!aadhaarNumber && !state.prefill.has_aadhaar) || !panNumber || !mobileNumber || !deviceImei}>
          {sendOtpMutation.isPending ? "Sending..." : "Send OTP"}
        </Button>
        <Field label="OTP" value={otp} onChangeText={setOtp} keyboardType="numeric" />
        <Button icon="check-decagram-outline" onPress={() => validateOtpMutation.mutate()} disabled={validateOtpMutation.isPending || !otp.trim()}>
          {validateOtpMutation.isPending ? "Validating..." : "Validate OTP"}
        </Button>
        <Button icon="refresh" variant="secondary" onPress={() => statusMutation.mutate()} disabled={statusMutation.isPending}>
          {statusMutation.isPending ? "Checking..." : "Check KYC Status"}
        </Button>
      </Grid>
      <Field label="Biometric Capture Response JSON" value={captureResponse} onChangeText={setCaptureResponse} multiline />
      <ErrorText message={error} />
      <Button icon="fingerprint" onPress={() => biometricMutation.mutate()} disabled={biometricMutation.isPending || !parseJsonObject(captureResponse) || !deviceImei}>
        {biometricMutation.isPending ? "Submitting..." : "Submit Biometric KYC"}
      </Button>
      {providerResponse ? (
        <Text selectable style={[styles.providerJson, { color: colors.muted, backgroundColor: colors.panelAlt }]}>
          {jsonPreview(providerResponse)}
        </Text>
      ) : null}
    </Panel>
  );
}

function AepsServicesPanel({ state }: { state: AepsProfileState }) {
  const { colors } = useTheme();
  const [transactionType, setTransactionType] = useState<"CW" | "BE" | "MS" | "M" | "CD">("CW");
  const [customerMobile, setCustomerMobile] = useState("");
  const [aadhaarNumber, setAadhaarNumber] = useState("");
  const [bankIin, setBankIin] = useState("");
  const [amount, setAmount] = useState("100");
  const [merchantPin, setMerchantPin] = useState("");
  const [deviceImei, setDeviceImei] = useState(state.profile?.device_imei || state.prefill.device_imei || "");
  const [latitude, setLatitude] = useState(String(state.profile?.latitude ?? state.prefill.latitude ?? ""));
  const [longitude, setLongitude] = useState(String(state.profile?.longitude ?? state.prefill.longitude ?? ""));
  const [captureResponse, setCaptureResponse] = useState("{}");
  const [result, setResult] = useState<Transaction | null>(null);
  const [providerResponse, setProviderResponse] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");

  const needsAmount = transactionType === "CW" || transactionType === "M" || transactionType === "CD";
  const parsedCapture = parseJsonObject(captureResponse);

  const mutation = useMutation({
    mutationFn: () => {
      if (!parsedCapture) throw new Error("Capture Response must be valid JSON.");
      return api.executeAepsTransaction({
        transaction_type: transactionType,
        customer_mobile: customerMobile,
        aadhaar_number: aadhaarNumber,
        bank_iin: bankIin,
        amount: needsAmount ? amount : "0",
        merchant_pin: merchantPin,
        capture_response: parsedCapture,
        device_imei: deviceImei,
        latitude: latitude || undefined,
        longitude: longitude || undefined,
      });
    },
    onSuccess: (response) => {
      setResult(response.transaction);
      setProviderResponse(response.provider_response);
      setError("");
    },
    onError: (err) => setError(err instanceof Error ? err.message : "AEPS transaction failed."),
  });

  const canSubmit =
    !!customerMobile.trim() &&
    !!aadhaarNumber.trim() &&
    !!bankIin.trim() &&
    !!merchantPin.trim() &&
    !!deviceImei.trim() &&
    !!parsedCapture &&
    (!needsAmount || (!!amount && Number(amount) > 0)) &&
    !mutation.isPending;

  return (
    <Panel title="AEPS Services">
      <AepsStatusPanel state={state} />
      <Grid>
        <SelectBox
          label="AEPS Service"
          value={transactionType}
          options={[
            { label: "Cash Withdrawal", value: "CW" },
            { label: "Balance Enquiry", value: "BE" },
            { label: "Mini Statement", value: "MS" },
            { label: "Aadhaar Pay", value: "M" },
            { label: "Cash Deposit", value: "CD" },
          ]}
          onChange={(value) => {
            setTransactionType(value as "CW" | "BE" | "MS" | "M" | "CD");
            if (value === "BE" || value === "MS") setAmount("0");
            if (value === "CW" && Number(amount) <= 0) setAmount("100");
          }}
        />
        <Field label="Customer Mobile" value={customerMobile} onChangeText={setCustomerMobile} keyboardType="phone-pad" />
        <Field label="Customer Aadhaar" value={aadhaarNumber} onChangeText={setAadhaarNumber} keyboardType="numeric" />
        <Field label="Bank IIN" value={bankIin} onChangeText={setBankIin} keyboardType="numeric" />
        {needsAmount ? <Field label="Amount" value={amount} onChangeText={setAmount} keyboardType="numeric" /> : null}
        <Field label="Merchant PIN" value={merchantPin} onChangeText={setMerchantPin} keyboardType="numeric" secureTextEntry />
        <Field label="Device IMEI / Serial" value={deviceImei} onChangeText={setDeviceImei} />
        <Field label="Latitude" value={latitude} onChangeText={setLatitude} keyboardType="numeric" />
        <Field label="Longitude" value={longitude} onChangeText={setLongitude} keyboardType="numeric" />
      </Grid>
      <Field label="Biometric Capture Response JSON" value={captureResponse} onChangeText={setCaptureResponse} multiline />
      <ErrorText message={error} />
      <Button icon="fingerprint" onPress={() => mutation.mutate()} disabled={!canSubmit}>
        {mutation.isPending ? "Processing..." : "Submit AEPS Transaction"}
      </Button>

      {result && (
        <View style={{ marginTop: 16 }}>
          <Text style={[styles.resultTitle, { color: colors.ink }]}>AEPS Result</Text>
          <DataTable
            data={[result]}
            keyExtractor={() => String(result.id)}
            columns={[
              { key: "ref", title: "Reference", width: 200, render: (r) => <Text selectable>{r.reference}</Text> },
              { key: "service", title: "Service", width: 190, render: (r) => <Text>{r.service_name ?? transactionType}</Text> },
              { key: "status", title: "Status", width: 130, render: (r) => <StatusBadge status={r.status} /> },
              { key: "amount", title: "Amount", width: 120, render: (r) => <Text>{money(r.amount)}</Text> },
              { key: "pref", title: "Provider Ref", width: 220, render: (r) => <Text selectable>{r.provider_reference || "N/A"}</Text> },
              { key: "date", title: "Date", width: 180, render: (r) => <Text>{dateTime(r.created_at)}</Text> },
            ]}
          />
        </View>
      )}

      {providerResponse ? (
        <Text selectable style={[styles.providerJson, { color: colors.muted, backgroundColor: colors.panelAlt }]}>
          {jsonPreview(providerResponse)}
        </Text>
      ) : null}
    </Panel>
  );
}

export function AepsTab() {
  const { colors } = useTheme();
  const query = useQuery({
    queryKey: ["aeps-profile"],
    queryFn: api.aepsProfile,
  });

  if (query.isLoading) {
    return (
      <Panel title="AEPS">
        <Text style={{ color: colors.muted, fontWeight: "700" }}>Loading AEPS profile...</Text>
      </Panel>
    );
  }

  if (query.isError || !query.data) {
    return (
      <Panel title="AEPS">
        <ErrorText message={query.error instanceof Error ? query.error.message : "Unable to load AEPS profile."} />
      </Panel>
    );
  }

  if (query.data.next_step === "merchant_onboarding") {
    return <AepsOnboardingForm state={query.data} />;
  }
  if (query.data.next_step === "ekyc") {
    return <AepsKycPanel state={query.data} />;
  }
  return <AepsServicesPanel state={query.data} />;
}

const styles = StyleSheet.create({
  statusRow: {
    borderRadius: 8,
    borderWidth: 1,
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12,
    padding: 12,
  },
  statusItem: {
    gap: 5,
    minWidth: 150,
  },
  statusLabel: {
    fontSize: 11,
    fontWeight: "900",
    textTransform: "uppercase",
  },
  statusValue: {
    fontSize: 13,
    fontWeight: "800",
  },
  providerJson: {
    borderRadius: 8,
    fontFamily: "monospace",
    fontSize: 12,
    lineHeight: 18,
    marginTop: 12,
    padding: 12,
  },
  resultTitle: {
    fontSize: 14,
    fontWeight: "700",
    marginBottom: 8,
  },
});
