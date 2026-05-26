import { useMutation, useQueryClient } from "@tanstack/react-query";
import React, { useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { api } from "@/api/client";
import {
  Button,
  DataTable,
  ErrorText,
  Field,
  Grid,
  Panel,
  Screen,
  SelectBox,
  StatusBadge,
} from "@/components/ui";
import { AepsTab } from "@/components/AepsServicePanel";
import { useTheme } from "@/context/ThemeContext";
import type { BBPSBillFetchResult, CMSResult, PayoutResult, Transaction } from "@/types";
import { dateTime, money } from "@/utils/format";

// ─── Helpers ─────────────────────────────────────────────────────────────────

function genOrderId(prefix = "QZ") {
  return `${prefix}${Date.now()}`;
}

// ─── Tab types ───────────────────────────────────────────────────────────────

type Tab = "aeps" | "payout" | "recharge" | "bbps" | "payin" | "cms" | "status";

const TABS: { id: Tab; label: string }[] = [
  { id: "aeps",     label: "AEPS" },
  { id: "payout",   label: "Payout" },
  { id: "recharge", label: "Recharge" },
  { id: "bbps",     label: "BBPS / Bill Pay" },
  { id: "payin",    label: "Payment Link" },
  { id: "cms",      label: "CMS" },
  { id: "status",   label: "Status Check" },
];

function TabBar({ active, onChange }: { active: Tab; onChange: (tab: Tab) => void }) {
  const { colors } = useTheme();
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      style={{ marginBottom: 16 }}
      contentContainerStyle={{ flexDirection: "row", gap: 8, paddingVertical: 4 }}
    >
      {TABS.map((tab) => {
        const isActive = tab.id === active;
        return (
          <Pressable
            key={tab.id}
            onPress={() => onChange(tab.id)}
            style={[
              styles.tab,
              {
                backgroundColor: isActive ? colors.brand : colors.panelAlt,
                borderColor: isActive ? colors.brand : colors.line,
              },
            ]}
          >
            <Text style={[styles.tabText, { color: isActive ? colors.white : colors.ink }]}>
              {tab.label}
            </Text>
          </Pressable>
        );
      })}
    </ScrollView>
  );
}

// ─── PAYOUT ──────────────────────────────────────────────────────────────────

function PayoutTab() {
  const [orderId, setOrderId]                 = useState(genOrderId("PAYOUT"));
  const [payoutPipe, setPayoutPipe]           = useState("bank1");
  const [amount, setAmount]                   = useState("1000");
  const [beneficiaryName, setBeneficiaryName] = useState("");
  const [accountNumber, setAccountNumber]     = useState("");
  const [ifsc, setIfsc]                       = useState("");
  const [bankName, setBankName]               = useState("");
  const [transferMode, setTransferMode]       = useState("IMPS");
  const [accountType, setAccountType]         = useState("SAVINGS");
  const [mobileNumber, setMobileNumber]       = useState("");
  const [remarks, setRemarks]                 = useState("Payment via QuickZaps");
  const [result, setResult]                   = useState<PayoutResult | null>(null);
  const [error, setError]                     = useState("");

  const { colors } = useTheme();

  const mutation = useMutation({
    mutationFn: () =>
      api.initiatePayout({
        OrderId: orderId,
        PayoutPipe: payoutPipe,
        Amount: amount,
        BeneficiaryName: beneficiaryName,
        AccountNumber: accountNumber,
        Ifsc: ifsc,
        BankName: bankName,
        TransferMode: transferMode,
        AccountType: accountType,
        MobileNumber: mobileNumber,
        Remarks: remarks,
      }),
    onSuccess: (response) => {
      setResult(response.data);
      setError("");
      setOrderId(genOrderId("PAYOUT"));
    },
    onError: (err) => setError(err instanceof Error ? err.message : "Payout initiation failed."),
  });

  const canSubmit =
    !!beneficiaryName.trim() &&
    !!accountNumber.trim() &&
    !!ifsc.trim() &&
    !!bankName.trim() &&
    !!mobileNumber.trim() &&
    !!amount &&
    Number(amount) > 0 &&
    !mutation.isPending;

  return (
    <Panel title="Payout — Bank Transfer">
      <Grid>
        <Field label="Order ID" value={orderId} onChangeText={setOrderId} placeholder="Unique order identifier" />
        <SelectBox
          label="Payout Route"
          value={payoutPipe}
          options={[
            { label: "EKO India (bank1)", value: "bank1" },
            { label: "Epesa (bank2)",     value: "bank2" },
            { label: "IDFC Bank (bank3)", value: "bank3" },
          ]}
          onChange={setPayoutPipe}
        />
        <Field label="Amount (₹)" value={amount} onChangeText={setAmount} keyboardType="numeric" placeholder="1000" />
        <Field label="Beneficiary Name" value={beneficiaryName} onChangeText={setBeneficiaryName} placeholder="John Doe" />
        <Field label="Account Number" value={accountNumber} onChangeText={setAccountNumber} keyboardType="numeric" placeholder="1234567890" />
        <Field label="IFSC Code" value={ifsc} onChangeText={setIfsc} placeholder="SBIN0001234" />
        <Field label="Bank Name" value={bankName} onChangeText={setBankName} placeholder="State Bank of India" />
        <SelectBox
          label="Transfer Mode"
          value={transferMode}
          options={[
            { label: "IMPS (Instant)",    value: "IMPS" },
            { label: "NEFT (Next Cycle)", value: "NEFT" },
            { label: "UPI",               value: "UPI" },
          ]}
          onChange={setTransferMode}
        />
        <SelectBox
          label="Account Type"
          value={accountType}
          options={[
            { label: "Savings", value: "SAVINGS" },
            { label: "Current", value: "CURRENT" },
          ]}
          onChange={setAccountType}
        />
        <Field label="Mobile Number" value={mobileNumber} onChangeText={setMobileNumber} keyboardType="phone-pad" placeholder="9876543210" />
        <Field label="Remarks" value={remarks} onChangeText={setRemarks} placeholder="Payment remarks" />
      </Grid>
      <ErrorText message={error} />
      <Button icon="bank-transfer" onPress={() => mutation.mutate()} disabled={!canSubmit}>
        {mutation.isPending ? "Processing…" : "Initiate Payout"}
      </Button>

      {result && (
        <View style={{ marginTop: 16 }}>
          <Text style={[styles.resultTitle, { color: colors.ink }]}>Payout Result</Text>
          <DataTable
            data={[result]}
            keyExtractor={() => result.OrderID}
            columns={[
              { key: "order",  title: "Order ID",   width: 200, render: (r) => <Text selectable>{r.OrderID}</Text> },
              { key: "tid",    title: "Txn ID",     width: 200, render: (r) => <Text selectable>{r.Tid || "—"}</Text> },
              { key: "amount", title: "Amount",     width: 120, render: (r) => <Text>{money(r.Amount)}</Text> },
              { key: "status", title: "Status",     width: 130, render: (r) => <StatusBadge status={r.TxStatus?.toLowerCase()} /> },
              { key: "utr",    title: "UTR",        width: 180, render: (r) => <Text selectable>{r.Utr || "N/A"}</Text> },
              { key: "acc",    title: "Account",    width: 160, render: (r) => <Text>{r.AccounNumber}</Text> },
              { key: "holder", title: "Holder",     width: 160, render: (r) => <Text>{r.AccountHolderName}</Text> },
              { key: "ifsc",   title: "IFSC",       width: 140, render: (r) => <Text>{r.IfscCode}</Text> },
            ]}
          />
        </View>
      )}
    </Panel>
  );
}

// ─── RECHARGE ────────────────────────────────────────────────────────────────

const TELECOM_CIRCLES = [
  { label: "Delhi",             value: "DL" },
  { label: "Maharashtra",       value: "MH" },
  { label: "Karnataka",         value: "KA" },
  { label: "Tamil Nadu",        value: "TN" },
  { label: "UP (East)",         value: "UPE" },
  { label: "UP (West)",         value: "UPW" },
  { label: "Gujarat",           value: "GJ" },
  { label: "Rajasthan",         value: "RJ" },
  { label: "West Bengal",       value: "WB" },
  { label: "Bihar & Jharkhand", value: "BR" },
  { label: "Odisha",            value: "OD" },
  { label: "Andhra Pradesh",    value: "AP" },
  { label: "Telangana",         value: "TG" },
  { label: "Punjab",            value: "PB" },
  { label: "Haryana",           value: "HR" },
  { label: "Madhya Pradesh",    value: "MP" },
  { label: "Assam",             value: "AS" },
  { label: "Kerala",            value: "KL" },
  { label: "Himachal Pradesh",  value: "HP" },
  { label: "Uttarakhand",       value: "UK" },
  { label: "North East",        value: "NE" },
];

const PREPAID_OPERATORS = [
  { label: "Airtel Prepaid",              value: "101" },
  { label: "Jio Prepaid",                value: "102" },
  { label: "Vi (Vodafone Idea) Prepaid", value: "103" },
  { label: "BSNL Prepaid",              value: "104" },
  { label: "MTNL Mumbai",               value: "105" },
  { label: "MTNL Delhi",                value: "106" },
];

const DTH_OPERATORS = [
  { label: "Tata Play (Tata Sky)",  value: "201" },
  { label: "Dish TV",               value: "202" },
  { label: "Sun Direct",            value: "203" },
  { label: "Airtel Digital TV",     value: "204" },
  { label: "D2H (Videocon)",        value: "205" },
];

function RechargeTab() {
  const [serviceType, setServiceType] = useState<"Prepaid" | "DTH">("Prepaid");
  const [mobileNumber, setMobileNumber] = useState("");
  const [operatorCode, setOperatorCode] = useState("101");
  const [amount, setAmount] = useState("199");
  const [circle, setCircle] = useState("DL");
  const [referenceId, setReferenceId] = useState(genOrderId("RCH"));
  const [result, setResult] = useState<Transaction | null>(null);
  const [error, setError] = useState("");

  const { colors } = useTheme();
  const operators = serviceType === "Prepaid" ? PREPAID_OPERATORS : DTH_OPERATORS;

  const mutation = useMutation({
    mutationFn: () =>
      api.initiateRecharge({
        OrderId: referenceId,
        ServiceType: serviceType,
        OperatorCode: operatorCode,
        MobileNumber: mobileNumber,
        Amount: amount,
        Circle: circle,
      }),
    onSuccess: (response) => {
      setResult(response.data);
      setError("");
      setReferenceId(genOrderId("RCH"));
    },
    onError: (err) => setError(err instanceof Error ? err.message : "Recharge failed."),
  });

  const canSubmit =
    !!mobileNumber.trim() && !!amount && Number(amount) > 0 && !mutation.isPending;

  return (
    <Panel title="Mobile & DTH Recharge">
      <Grid>
        <SelectBox
          label="Service Type"
          value={serviceType}
          options={[
            { label: "Prepaid Recharge", value: "Prepaid" },
            { label: "DTH Recharge",     value: "DTH" },
          ]}
          onChange={(v) => {
            const t = v as "Prepaid" | "DTH";
            setServiceType(t);
            setOperatorCode(t === "DTH" ? "201" : "101");
          }}
        />
        <SelectBox label="Operator" value={operatorCode} options={operators} onChange={setOperatorCode} />
        <Field
          label="Mobile / Subscriber Number"
          value={mobileNumber}
          onChangeText={setMobileNumber}
          keyboardType="phone-pad"
          placeholder={serviceType === "Prepaid" ? "9876543210" : "Subscriber ID"}
        />
        <Field label="Amount (₹)" value={amount} onChangeText={setAmount} keyboardType="numeric" placeholder="199" />
        <SelectBox label="Telecom Circle" value={circle} options={TELECOM_CIRCLES} onChange={setCircle} />
        <Field label="Reference ID" value={referenceId} onChangeText={setReferenceId} placeholder="Unique reference" />
      </Grid>
      <ErrorText message={error} />
      <Button icon="cellphone-wireless" onPress={() => mutation.mutate()} disabled={!canSubmit}>
        {mutation.isPending ? "Processing…" : "Initiate Recharge"}
      </Button>

      {result && (
        <View style={{ marginTop: 16 }}>
          <Text style={[styles.resultTitle, { color: colors.ink }]}>Recharge Result</Text>
          <DataTable
            data={[result]}
            keyExtractor={() => String(result.reference ?? result.id)}
            columns={[
              { key: "ref",    title: "Reference",    width: 200, render: (r) => <Text selectable>{r.reference}</Text> },
              { key: "status", title: "Status",       width: 130, render: (r) => <StatusBadge status={r.status} /> },
              { key: "amount", title: "Amount",       width: 120, render: (r) => <Text>{money(r.amount)}</Text> },
              { key: "pref",   title: "Provider Ref", width: 220, render: (r) => <Text selectable>{r.provider_reference || "N/A"}</Text> },
              { key: "date",   title: "Date",         width: 180, render: (r) => <Text>{dateTime(r.created_at)}</Text> },
            ]}
          />
        </View>
      )}
    </Panel>
  );
}

// ─── BBPS (Bill Payment) ──────────────────────────────────────────────────────

const BBPS_ELECTRICITY_OPERATORS = [
  { label: "BSES Rajdhani Power",  value: "501" },
  { label: "BSES Yamuna Power",    value: "502" },
  { label: "Tata Power Delhi",     value: "503" },
  { label: "UPPCL (Purvanchal)",   value: "504" },
  { label: "UPPCL (Madhyanchal)",  value: "505" },
  { label: "UPPCL (Pascimanchal)", value: "506" },
  { label: "MSEDCL (Maharashtra)", value: "507" },
  { label: "BESCOM (Karnataka)",   value: "508" },
  { label: "TNEB (Tamil Nadu)",    value: "509" },
  { label: "CESC (West Bengal)",   value: "510" },
  { label: "JDVVNL (Rajasthan)",   value: "511" },
];

const BBPS_INSURANCE_OPERATORS = [
  { label: "LIC India",             value: "601" },
  { label: "HDFC Life Insurance",   value: "602" },
  { label: "ICICI Prudential Life", value: "603" },
  { label: "SBI Life Insurance",    value: "604" },
  { label: "Max Life Insurance",    value: "605" },
  { label: "Tata AIA Life",         value: "606" },
  { label: "Bajaj Allianz Life",    value: "607" },
];

function BBPSTab() {
  const [step, setStep]               = useState<"fetch" | "pay">("fetch");
  const [serviceType, setServiceType] = useState("electricity");
  const [consumerNo, setConsumerNo]   = useState("");
  const [operatorCode, setOperatorCode] = useState("501");
  const [mobileNumber, setMobileNumber] = useState("");
  const [emailId, setEmailId]         = useState("");
  const [dob, setDob]                 = useState("");

  const [orderId, setOrderId]         = useState(genOrderId("BBPS"));
  const [payAmount, setPayAmount]     = useState("");
  const [consumerName, setConsumerName] = useState("");
  const [latitude, setLatitude]       = useState("28.6139");
  const [longitude, setLongitude]     = useState("77.2090");

  const [fetchResult, setFetchResult] = useState<BBPSBillFetchResult | null>(null);
  const [payResult, setPayResult]     = useState<Transaction | null>(null);
  const [error, setError]             = useState("");

  const { colors } = useTheme();
  const operators =
    serviceType === "electricity" ? BBPS_ELECTRICITY_OPERATORS : BBPS_INSURANCE_OPERATORS;

  const fetchMutation = useMutation({
    mutationFn: () =>
      api.bbpsFetchBill({
        ServiceType: serviceType,
        OperatorCode: operatorCode,
        ConsumerNo: consumerNo,
        MobileNumber: mobileNumber,
        EmailId: emailId,
        Dob: dob || undefined,
        Amount: "500",
      }),
    onSuccess: (response) => {
      const data = response.data;
      setFetchResult(data);
      setPayAmount(String(data.bill_amount || ""));
      setConsumerName(data.customer_name || "");
      setStep("pay");
      setError("");
    },
    onError: (err) => setError(err instanceof Error ? err.message : "Bill fetch failed."),
  });

  const payMutation = useMutation({
    mutationFn: () =>
      api.bbpsPayBill({
        OrderId: orderId,
        ServiceType: serviceType,
        OperatorCode: operatorCode,
        Amount: payAmount,
        ConsumerNo: consumerNo,
        ConsumerName: consumerName,
        ReferenceId: fetchResult?.reference_id ?? orderId,
        MobileNumber: mobileNumber,
        EmailId: emailId || undefined,
        Latitude: latitude,
        Longitude: longitude,
      }),
    onSuccess: (response) => {
      setPayResult(response.data);
      setError("");
      setOrderId(genOrderId("BBPS"));
    },
    onError: (err) => setError(err instanceof Error ? err.message : "Bill payment failed."),
  });

  const resetFetch = () => {
    setStep("fetch");
    setFetchResult(null);
    setPayResult(null);
    setError("");
  };

  return (
    <Panel title="BBPS — Utility Bill Payment">
      {step === "fetch" ? (
        <>
          <Grid>
            <SelectBox
              label="Service Type"
              value={serviceType}
              options={[
                { label: "Electricity", value: "electricity" },
                { label: "Insurance",   value: "insurance" },
              ]}
              onChange={(v) => {
                setServiceType(v);
                setOperatorCode(v === "electricity" ? "501" : "601");
                setFetchResult(null);
              }}
            />
            <SelectBox
              label="Operator / Provider"
              value={operatorCode}
              options={operators}
              onChange={setOperatorCode}
            />
            <Field label="Consumer / Policy Number" value={consumerNo} onChangeText={setConsumerNo} placeholder="1234567890" />
            <Field label="Mobile Number" value={mobileNumber} onChangeText={setMobileNumber} keyboardType="phone-pad" placeholder="9876543210" />
            <Field label="Email ID" value={emailId} onChangeText={setEmailId} keyboardType="email-address" placeholder="user@email.com" />
            {serviceType === "insurance" && (
              <Field label="Date of Birth (DD-MM-YYYY)" value={dob} onChangeText={setDob} placeholder="01-01-1990" />
            )}
          </Grid>
          <ErrorText message={error} />
          <Button
            icon="file-find-outline"
            onPress={() => fetchMutation.mutate()}
            disabled={fetchMutation.isPending || !consumerNo.trim() || !mobileNumber.trim()}
          >
            {fetchMutation.isPending ? "Fetching Bill…" : "Fetch Bill Details"}
          </Button>
        </>
      ) : (
        <>
          {fetchResult && (
            <View
              style={{
                marginBottom: 16,
                padding: 14,
                backgroundColor: colors.panelAlt,
                borderRadius: 10,
                gap: 6,
                borderLeftWidth: 4,
                borderLeftColor: colors.brand,
              }}
            >
              <Text style={[styles.resultTitle, { color: colors.ink }]}>Fetched Bill</Text>
              <Text style={{ color: colors.muted }}>
                Consumer:{" "}
                <Text style={{ color: colors.ink, fontWeight: "700" }}>{fetchResult.customer_name}</Text>
              </Text>
              <Text style={{ color: colors.muted }}>
                Consumer No: <Text style={{ color: colors.ink }}>{fetchResult.consumer_number}</Text>
              </Text>
              <Text style={{ color: colors.muted }}>
                Bill Amount:{" "}
                <Text style={{ color: colors.brand, fontWeight: "700" }}>
                  {money(fetchResult.bill_amount)}
                </Text>
              </Text>
              <Text style={{ color: colors.muted }}>
                Due Date: <Text style={{ color: colors.ink }}>{fetchResult.due_date}</Text>
              </Text>
              <Text style={{ color: colors.muted }}>
                Reference:{" "}
                <Text selectable style={{ color: colors.ink }}>{fetchResult.reference_id}</Text>
              </Text>
            </View>
          )}

          <Grid>
            <Field label="Order ID" value={orderId} onChangeText={setOrderId} placeholder="Unique order identifier" />
            <Field label="Amount (₹)" value={payAmount} onChangeText={setPayAmount} keyboardType="numeric" placeholder="Amount to pay" />
            <Field label="Consumer Name" value={consumerName} onChangeText={setConsumerName} placeholder="Customer name" />
            <Field label="Latitude" value={latitude} onChangeText={setLatitude} keyboardType="numeric" />
            <Field label="Longitude" value={longitude} onChangeText={setLongitude} keyboardType="numeric" />
          </Grid>

          <ErrorText message={error} />

          <Grid>
            <Button icon="arrow-left" variant="ghost" onPress={resetFetch}>← Back to Fetch</Button>
            <Button
              icon="cash-check"
              onPress={() => payMutation.mutate()}
              disabled={payMutation.isPending || !payAmount || Number(payAmount) <= 0}
            >
              {payMutation.isPending ? "Paying…" : "Pay Bill"}
            </Button>
          </Grid>

          {payResult && (
            <View style={{ marginTop: 16 }}>
              <Text style={[styles.resultTitle, { color: colors.ink }]}>Payment Result</Text>
              <DataTable
                data={[payResult]}
                keyExtractor={() => String(payResult.reference ?? payResult.id)}
                columns={[
                  { key: "ref",    title: "Reference",    width: 200, render: (r) => <Text selectable>{r.reference}</Text> },
                  { key: "status", title: "Status",       width: 130, render: (r) => <StatusBadge status={r.status} /> },
                  { key: "amount", title: "Amount",       width: 120, render: (r) => <Text>{money(r.amount)}</Text> },
                  { key: "pref",   title: "Provider Ref", width: 220, render: (r) => <Text selectable>{r.provider_reference || "N/A"}</Text> },
                ]}
              />
            </View>
          )}
        </>
      )}
    </Panel>
  );
}

// ─── PAYMENT LINK (PAYIN) ─────────────────────────────────────────────────────

function PayinTab() {
  const queryClient = useQueryClient();
  const [orderId, setOrderId]               = useState(genOrderId("PAYIN"));
  const [payinType, setPayinType]           = useState("upi");
  const [amount, setAmount]                 = useState("500");
  const [beneficiaryName, setBeneficiaryName] = useState("");
  const [mobileNumber, setMobileNumber]     = useState("");
  const [emailId, setEmailId]               = useState("");
  const [result, setResult]                 = useState<Record<string, unknown> | null>(null);
  const [error, setError]                   = useState("");

  const { colors } = useTheme();

  const mutation = useMutation({
    mutationFn: () =>
      api.createPayinLink({
        OrderId: orderId,
        PayinType: payinType,
        Amount: amount,
        BeneficiaryName: beneficiaryName,
        MobileNumber: mobileNumber,
        EmailID: emailId,
      }),
    onSuccess: (response) => {
      setResult(response.data);
      setError("");
      setOrderId(genOrderId("PAYIN"));
      queryClient.invalidateQueries({ queryKey: ["wallet-mine"] });
    },
    onError: (err) =>
      setError(err instanceof Error ? err.message : "Payment link creation failed."),
  });

  const canSubmit =
    !!amount && Number(amount) > 0 && !!beneficiaryName.trim() && !!mobileNumber.trim() && !mutation.isPending;

  return (
    <Panel title="Payin — Create Payment Collection Link">
      <Grid>
        <Field label="Order ID" value={orderId} onChangeText={setOrderId} placeholder="Unique order identifier" />
        <SelectBox
          label="Payment Type"
          value={payinType}
          options={[
            { label: "UPI",         value: "upi" },
            { label: "Net Banking", value: "netbanking" },
            { label: "Card",        value: "card" },
          ]}
          onChange={setPayinType}
        />
        <Field label="Amount (₹)" value={amount} onChangeText={setAmount} keyboardType="numeric" placeholder="500" />
        <Field label="Customer Name" value={beneficiaryName} onChangeText={setBeneficiaryName} placeholder="Customer Name" />
        <Field label="Mobile Number" value={mobileNumber} onChangeText={setMobileNumber} keyboardType="phone-pad" placeholder="9876543210" />
        <Field label="Email ID" value={emailId} onChangeText={setEmailId} keyboardType="email-address" placeholder="customer@email.com" />
      </Grid>
      <ErrorText message={error} />
      <Button icon="link-variant" onPress={() => mutation.mutate()} disabled={!canSubmit}>
        {mutation.isPending ? "Creating…" : "Create Payment Link"}
      </Button>

      {result && (
        <View
          style={{
            marginTop: 16,
            padding: 14,
            backgroundColor: colors.panelAlt,
            borderRadius: 10,
            gap: 8,
          }}
        >
          <Text style={[styles.resultTitle, { color: colors.ink }]}>Payment Link Created</Text>
          <Text style={{ color: colors.muted }}>
            Order ID: <Text style={{ color: colors.ink }}>{String(result.OrderID ?? result.reference ?? "—")}</Text>
          </Text>
          <Text style={{ color: colors.muted }}>
            Amount:{" "}
            <Text style={{ color: colors.brand, fontWeight: "700" }}>
              {money((result.Amount ?? result.amount) as string | number | null | undefined)}
            </Text>
          </Text>
          <Text style={{ color: colors.muted }}>
            Status:{" "}
            <Text style={{ color: colors.ink }}>{String(result.Status ?? result.status ?? "—")}</Text>
          </Text>
          {(result.PaymentLink || result.payment_link) ? (
            <>
              <Text style={{ color: colors.muted, marginTop: 4 }}>Payment Link:</Text>
              <Text selectable style={[styles.linkText, { color: colors.brand }]}>
                {String(result.PaymentLink ?? result.payment_link)}
              </Text>
            </>
          ) : null}
          {result.RazorpayPaymentLinkId ? (
            <Text style={{ color: colors.muted }}>
              Link ID: <Text style={{ color: colors.ink }}>{String(result.RazorpayPaymentLinkId)}</Text>
            </Text>
          ) : null}
          {result.provider_reference ? (
            <Text style={{ color: colors.muted }}>
              Provider Ref:{" "}
              <Text selectable style={{ color: colors.ink }}>{String(result.provider_reference)}</Text>
            </Text>
          ) : null}
        </View>
      )}
    </Panel>
  );
}

// ─── CMS ──────────────────────────────────────────────────────────────────────

function CMSTab() {
  const [mobileNumber, setMobileNumber] = useState("");
  const [orderId, setOrderId]           = useState(genOrderId("CMS"));
  const [result, setResult]             = useState<CMSResult | null>(null);
  const [error, setError]               = useState("");

  const { colors } = useTheme();

  const mutation = useMutation({
    mutationFn: () =>
      api.initiateCMS({ MobileNumber: mobileNumber, OrderId: orderId }),
    onSuccess: (response) => {
      setResult(response.data);
      setError("");
      setOrderId(genOrderId("CMS"));
    },
    onError: (err) =>
      setError(err instanceof Error ? err.message : "CMS initiation failed."),
  });

  return (
    <Panel title="CMS — Cash Management Service (Airtel)">
      <Text style={{ color: colors.muted, marginBottom: 12, lineHeight: 20 }}>
        Initiate an Airtel CMS session for a retailer mobile number. A redirect URL will be
        returned to complete the cash deposit / withdrawal at the retailer outlet.
      </Text>
      <Grid>
        <Field
          label="Retailer Mobile Number"
          value={mobileNumber}
          onChangeText={setMobileNumber}
          keyboardType="phone-pad"
          placeholder="9876543210"
        />
        <Field
          label="Transaction ID"
          value={orderId}
          onChangeText={setOrderId}
          placeholder="Unique transaction identifier"
        />
      </Grid>
      <ErrorText message={error} />
      <Button
        icon="cash-sync"
        onPress={() => mutation.mutate()}
        disabled={mutation.isPending || !mobileNumber.trim()}
      >
        {mutation.isPending ? "Initiating…" : "Start CMS Session"}
      </Button>

      {result && (
        <View
          style={{
            marginTop: 16,
            padding: 14,
            backgroundColor: colors.panelAlt,
            borderRadius: 10,
            gap: 8,
          }}
        >
          <Text style={[styles.resultTitle, { color: colors.ink }]}>CMS Session Created</Text>
          <Text style={{ color: colors.muted }}>
            Transaction ID:{" "}
            <Text selectable style={{ color: colors.ink }}>{result.transaction_id}</Text>
          </Text>
          <Text style={{ color: colors.muted }}>
            Mobile: <Text style={{ color: colors.ink }}>{result.mobile_number}</Text>
          </Text>
          <Text style={{ color: colors.muted }}>
            Status: <Text style={{ color: colors.ink, fontWeight: "600" }}>{result.status}</Text>
          </Text>
          {result.redirect_url ? (
            <>
              <Text style={{ color: colors.muted, marginTop: 4 }}>Redirect URL:</Text>
              <Text selectable style={[styles.linkText, { color: colors.brand }]}>
                {result.redirect_url}
              </Text>
            </>
          ) : null}
        </View>
      )}
    </Panel>
  );
}

// ─── STATUS CHECK ─────────────────────────────────────────────────────────────

function StatusCheckTab() {
  const [orderId, setOrderId] = useState("");
  const [result, setResult]   = useState<Transaction | null>(null);
  const [error, setError]     = useState("");

  const { colors } = useTheme();

  const mutation = useMutation({
    mutationFn: () =>
      api.partnerTransactionStatus({ OrderId: orderId }),
    onSuccess: (response) => {
      setResult(response.data);
      setError("");
    },
    onError: (err) =>
      setError(err instanceof Error ? err.message : "Transaction not found or status check failed."),
  });

  return (
    <Panel title="Transaction Status Check">
      <Text style={{ color: colors.muted, marginBottom: 12, lineHeight: 20 }}>
        Enter an Order ID or Transaction Reference to check the current status of any
        previously initiated transaction (Payout, Recharge, BBPS, etc.).
      </Text>
      <Grid>
        <Field
          label="Order ID / Reference"
          value={orderId}
          onChangeText={setOrderId}
          placeholder="e.g. PAYOUT1234567890"
        />
        <Button
          icon="magnify"
          onPress={() => mutation.mutate()}
          disabled={mutation.isPending || !orderId.trim()}
        >
          {mutation.isPending ? "Checking…" : "Check Status"}
        </Button>
      </Grid>
      <ErrorText message={error} />

      {result && (
        <View style={{ marginTop: 16 }}>
          <DataTable
            data={[result]}
            keyExtractor={() => String(result.id)}
            columns={[
              { key: "ref",    title: "Reference",       width: 200, render: (r) => <Text selectable>{r.reference}</Text> },
              { key: "service",title: "Service",         width: 160, render: (r) => <Text>{r.service_name ?? "—"}</Text> },
              { key: "op",     title: "Operator",        width: 160, render: (r) => <Text>{r.operator_name ?? "—"}</Text> },
              { key: "status", title: "Status",          width: 130, render: (r) => <StatusBadge status={r.status} /> },
              { key: "amount", title: "Amount",          width: 120, render: (r) => <Text>{money(r.amount)}</Text> },
              { key: "pref",   title: "Provider Ref",    width: 200, render: (r) => <Text selectable>{r.provider_reference || "N/A"}</Text> },
              { key: "mob",    title: "Customer Mobile", width: 150, render: (r) => <Text>{r.customer_mobile || "—"}</Text> },
              { key: "date",   title: "Date",            width: 180, render: (r) => <Text>{dateTime(r.created_at)}</Text> },
            ]}
          />
        </View>
      )}
    </Panel>
  );
}

// ─── ROOT COMPONENT ───────────────────────────────────────────────────────────

export default function UserServices() {
  const [activeTab, setActiveTab] = useState<Tab>("aeps");

  return (
    <Screen title="Services">
      <TabBar active={activeTab} onChange={setActiveTab} />
      {activeTab === "aeps"     && <AepsTab />}
      {activeTab === "payout"   && <PayoutTab />}
      {activeTab === "recharge" && <RechargeTab />}
      {activeTab === "bbps"     && <BBPSTab />}
      {activeTab === "payin"    && <PayinTab />}
      {activeTab === "cms"      && <CMSTab />}
      {activeTab === "status"   && <StatusCheckTab />}
    </Screen>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  tab: {
    paddingHorizontal: 16,
    paddingVertical: 9,
    borderRadius: 20,
    borderWidth: 1.5,
    minWidth: 80,
    alignItems: "center",
  },
  tabText: {
    fontSize: 13,
    fontWeight: "600",
    letterSpacing: 0.2,
  },
  resultTitle: {
    fontSize: 14,
    fontWeight: "700",
    marginBottom: 8,
  },
  linkText: {
    fontSize: 13,
    fontWeight: "600",
    textDecorationLine: "underline",
  },
});
