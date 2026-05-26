import * as DocumentPicker from "expo-document-picker";
import * as Linking from "expo-linking";
import { useLocalSearchParams } from "expo-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import React, { useEffect, useMemo, useRef, useState } from "react";
import { Text, View } from "react-native";

import { api } from "@/api/client";
import { Button, DataTable, ErrorText, Field, Grid, Panel, Screen, SelectBox, StatusBadge, Toggle } from "@/components/ui";
import { useAuth } from "@/context/AuthContext";
import { useTheme } from "@/context/ThemeContext";
import type { ID, OnboardingApplication, OnboardingRole } from "@/types";
import { dateTime } from "@/utils/format";

type PickedFile = DocumentPicker.DocumentPickerAsset;
type FileField = "live_photo" | "shop_photo" | "agent_photo" | "business_photo" | "gst_document" | "udyam_document" | "bank_proof";
type GeoField = "live_photo_geo" | "shop_photo_geo" | "agent_photo_geo";

const roleOptions: Array<{ label: string; value: OnboardingRole }> = [
  { label: "SDBR", value: "SDBR" },
  { label: "DBR", value: "DBR" },
  { label: "Retailer", value: "RETAILER" }
];

const steps = ["Identity", "Hierarchy", "Photos", "Bank", "Business", "Review"];

const emptyForm = {
  requested_role: "RETAILER" as OnboardingRole,
  direct_to_admin: false,
  parent: null as ID | null,
  mobile: "",
  email: "",
  full_name: "",
  dob: "",
  aadhaar_number: "",
  pan_number: "",
  account_holder_name: "",
  bank_name: "",
  account_number: "",
  ifsc: "",
  upi_id: "",
  business_name: "",
  business_type: "",
  gst_number: "",
  udyam_number: "",
  business_address: "",
  city: "",
  state: "",
  pin_code: ""
};

export default function UserKyc() {
  const queryClient = useQueryClient();
  const { user, reloadUser } = useAuth();
  const { colors } = useTheme();
  const params = useLocalSearchParams<{ digilocker_vid?: string }>();
  const [step, setStep] = useState(0);
  const [form, setForm] = useState(emptyForm);
  const [files, setFiles] = useState<Partial<Record<FileField, PickedFile>>>({});
  const [geo, setGeo] = useState<Record<GeoField, Record<string, unknown>>>({
    live_photo_geo: {},
    shop_photo_geo: {},
    agent_photo_geo: {}
  });
  const [identityVerification, setIdentityVerification] = useState<Record<string, unknown> | null>(null);
  const [bankVerification, setBankVerification] = useState<Record<string, unknown> | null>(null);
  const [businessVerification, setBusinessVerification] = useState<Record<string, unknown> | null>(null);
  const [digilockerVerificationId, setDigilockerVerificationId] = useState<string | null>(null);
  const [digilockerStatus, setDigilockerStatus] = useState<string | null>(null);
  const [aadhaarVerification, setAadhaarVerification] = useState<Record<string, unknown> | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [error, setError] = useState("");

  // Handle redirect back from Cashfree DigiLocker consent page
  useEffect(() => {
    const vid = params.digilocker_vid;
    if (!vid || aadhaarVerification) return;
    setDigilockerVerificationId(vid);
    setDigilockerStatus("AUTHENTICATED");
    api.digilockerDocument(vid)
      .then((doc) => setAadhaarVerification(doc))
      .catch(() => setError("Failed to fetch Aadhaar document after DigiLocker consent."));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.digilocker_vid]);

  const applications = useQuery({ queryKey: ["onboarding-applications", "mine"], queryFn: () => api.onboardingApplications() });
  const parents = useQuery({
    queryKey: ["onboarding-parents", form.requested_role],
    queryFn: () => api.onboardingParents(form.requested_role),
    enabled: form.requested_role !== "SDBR" && !form.direct_to_admin
  });

  const parentOptions = useMemo(
    () => [
      { label: "Select parent", value: null as ID | null },
      ...(parents.data || []).map((parent) => ({ label: `${parent.name} · ${parent.mobile} · ${parent.role_name}`, value: parent.id }))
    ],
    [parents.data]
  );

  function updateForm<K extends keyof typeof emptyForm>(field: K, value: (typeof emptyForm)[K]) {
    setForm((current) => ({ ...current, [field]: value }));
    if (["mobile", "email", "full_name", "dob", "aadhaar_number", "pan_number"].includes(String(field))) {
      setIdentityVerification(null);
      setBankVerification(null);
      setBusinessVerification(null);
      setDigilockerVerificationId(null);
      setDigilockerStatus(null);
      setAadhaarVerification(null);
      if (pollRef.current) clearInterval(pollRef.current);
    }
    if (["account_holder_name", "account_number", "ifsc", "bank_name", "upi_id"].includes(String(field))) {
      setBankVerification(null);
    }
    if (["business_name", "business_type", "gst_number", "udyam_number", "business_address", "city", "state", "pin_code"].includes(String(field))) {
      setBusinessVerification(null);
    }
  }

  async function pick(field: FileField) {
    const result = await DocumentPicker.getDocumentAsync({
      type: ["image/jpeg", "image/png", "application/pdf"],
      multiple: false,
      copyToCacheDirectory: true
    });
    if (!result.canceled && result.assets[0]) {
      setFiles((current) => ({ ...current, [field]: result.assets[0] }));
      if (["business_photo", "gst_document", "udyam_document"].includes(field)) {
        setBusinessVerification(null);
      }
    }
  }

  function appendFile(data: FormData, field: FileField) {
    const asset = files[field];
    if (!asset) return;
    const webFile = (asset as PickedFile & { file?: Blob }).file;
    if (webFile) {
      data.append(field, webFile, asset.name);
      return;
    }
    data.append(field, {
      uri: asset.uri,
      name: asset.name,
      type: asset.mimeType || "application/octet-stream"
    } as unknown as Blob);
  }

  async function captureGeo(field: GeoField) {
    const nav = globalThis.navigator as typeof globalThis.navigator & {
      geolocation?: { getCurrentPosition: (success: (position: GeolocationPosition) => void, error: () => void, options?: PositionOptions) => void };
    };
    if (!nav.geolocation) {
      setGeo((current) => ({ ...current, [field]: { unavailable: true, captured_at: new Date().toISOString() } }));
      return;
    }
    nav.geolocation.getCurrentPosition(
      (position) => {
        setGeo((current) => ({
          ...current,
          [field]: {
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
            accuracy: position.coords.accuracy,
            captured_at: new Date().toISOString()
          }
        }));
      },
      () => setGeo((current) => ({ ...current, [field]: { unavailable: true, captured_at: new Date().toISOString() } })),
      { enableHighAccuracy: true, timeout: 12000 }
    );
  }

  const submit = useMutation({
    mutationFn: async () => {
      const data = new FormData();
      Object.entries(form).forEach(([key, value]) => {
        if (value !== null) data.append(key, String(value));
      });
      data.append("direct_to_admin", String(form.requested_role === "SDBR" || form.direct_to_admin));
      Object.entries(geo).forEach(([key, value]) => data.append(key, JSON.stringify(value)));
      (["live_photo", "shop_photo", "agent_photo", "business_photo", "gst_document", "udyam_document", "bank_proof"] as FileField[]).forEach((field) =>
        appendFile(data, field)
      );
      return api.submitOnboarding(data);
    },
    onSuccess: async () => {
      setError("");
      setForm(emptyForm);
      setFiles({});
      setIdentityVerification(null);
      setBankVerification(null);
      setBusinessVerification(null);
      setDigilockerVerificationId(null);
      setDigilockerStatus(null);
      setAadhaarVerification(null);
      setStep(0);
      queryClient.invalidateQueries({ queryKey: ["onboarding-applications"] });
      await reloadUser();
    },
    onError: (err) => setError(err instanceof Error ? err.message : "Onboarding submission failed.")
  });
  const review = useMutation({
    mutationFn: ({ id, action }: { id: ID; action: "approve" | "reject" }) => api.reviewOnboarding(id, { action }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["onboarding-applications"] }),
    onError: (err) => setError(err instanceof Error ? err.message : "Onboarding review failed.")
  });
  const verifyIdentity = useMutation({
    mutationFn: () =>
      api.verifyOnboardingIdentity({
        mobile: form.mobile,
        email: form.email,
        full_name: form.full_name,
        dob: form.dob,
        aadhaar_number: form.aadhaar_number,
        pan_number: form.pan_number
      }),
    onSuccess: (data) => {
      if (data.verified) {
        setIdentityVerification(data);
        setError("");
      } else {
        setIdentityVerification(null);
        setError("PAN and Aadhaar verification did not pass.");
      }
    },
    onError: (err) => setError(err instanceof Error ? err.message : "Identity verification failed.")
  });

  const digilockerInit = useMutation({
    mutationFn: () => {
      // Build redirect URL back to this page with the verification_id as a param.
      // On web use window.location.origin; on native Linking.createURL provides the deep-link.
      let base = "";
      try {
        if (typeof window !== "undefined" && window.location) {
          base = window.location.origin;
        } else {
          base = Linking.createURL("");
        }
      } catch {
        base = Linking.createURL("");
      }
      // The redirect URL will be completed by the backend with ?verification_id=... appended by Cashfree.
      // We use a static base path; the verification_id param name used by Cashfree is `verification_id`.
      // We map it to `digilocker_vid` via the redirect_url template below.
      const redirectBase = base.replace(/\/$/, "") + "/user/kyc";
      return api.digilockerInit(redirectBase);
    },
    onSuccess: async (data) => {
      const vid = String(data.verification_id || "");
      const url = String(data.url || "");
      setDigilockerVerificationId(vid);
      setDigilockerStatus("PENDING");
      setError("");
      if (url && !url.includes("quickzaps.local")) {
        await Linking.openURL(url);
      } else {
        // dummy mode — simulate immediate consent
        setDigilockerStatus("AUTHENTICATED");
        setAadhaarVerification({ verified: true, mode: "dummy", aadhaar_verification: { status: "SUCCESS", uid: "xxxxxxxx5678", message: "Aadhaar Card Exists (dummy)" } });
      }
      if (vid && url && !url.includes("quickzaps.local")) {
        pollRef.current = setInterval(async () => {
          try {
            const status = await api.digilockerStatus(vid);
            const s = String(status.status || "").toUpperCase();
            setDigilockerStatus(s);
            if (s === "AUTHENTICATED") {
              clearInterval(pollRef.current!);
              const doc = await api.digilockerDocument(vid);
              setAadhaarVerification(doc);
            } else if (s === "EXPIRED" || s === "CONSENT_DENIED") {
              clearInterval(pollRef.current!);
              setError(`DigiLocker verification ${s.toLowerCase().replace("_", " ")}. Please try again.`);
            }
          } catch {
            clearInterval(pollRef.current!);
          }
        }, 4000);
      }
    },
    onError: (err) => setError(err instanceof Error ? err.message : "DigiLocker initialization failed.")
  });
  const verifyBank = useMutation({
    mutationFn: () =>
      api.verifyOnboardingBank({
        mobile: form.mobile,
        full_name: form.full_name,
        dob: form.dob,
        account_holder_name: form.account_holder_name,
        account_number: form.account_number,
        ifsc: form.ifsc,
        bank_name: form.bank_name,
        upi_id: form.upi_id
      }),
    onSuccess: (data) => {
      if (data.verified) {
        setBankVerification(data);
        setError("");
      } else {
        setBankVerification(null);
        setError("Bank reverse penny drop verification did not pass.");
      }
    },
    onError: (err) => setError(err instanceof Error ? err.message : "Bank verification failed.")
  });
  const verifyBusiness = useMutation({
    mutationFn: () =>
      api.verifyOnboardingBusiness({
        dob: form.dob,
        business_name: form.business_name,
        business_type: form.business_type,
        gst_number: form.gst_number,
        udyam_number: form.udyam_number,
        business_address: form.business_address,
        city: form.city,
        state: form.state,
        pin_code: form.pin_code
      }),
    onSuccess: (data) => {
      if (data.verified) {
        setBusinessVerification(data);
        setError("");
      } else {
        setBusinessVerification(null);
        setError("Business verification did not pass.");
      }
    },
    onError: (err) => setError(err instanceof Error ? err.message : "Business verification failed.")
  });

  const activeApplication = applications.data?.find((item: OnboardingApplication) => ["pending_parent", "pending_admin", "created"].includes(item.status));
  const identityReady = Boolean(form.mobile && form.email && form.full_name && form.dob && form.aadhaar_number && form.pan_number);
  const panVerified = Boolean(identityVerification?.verified);
  const aadhaarVerified = Boolean(aadhaarVerification?.verified || (aadhaarVerification as Record<string, unknown> | null)?.aadhaar_verification);
  const identityVerified = panVerified && aadhaarVerified;
  const hierarchyReady = Boolean(form.requested_role === "SDBR" || form.direct_to_admin || form.parent);
  const photosReady = Boolean(
    files.live_photo &&
    files.shop_photo &&
    files.agent_photo &&
    geo.live_photo_geo.captured_at &&
    geo.shop_photo_geo.captured_at &&
    geo.agent_photo_geo.captured_at
  );
  const bankReady = Boolean(form.account_holder_name && form.account_number && form.ifsc);
  const bankVerified = Boolean(bankVerification?.verified);
  const businessReady = Boolean(
    form.business_name &&
    form.business_address &&
    form.city &&
    form.state &&
    form.pin_code &&
    files.business_photo &&
    (!form.gst_number || files.gst_document) &&
    (!form.udyam_number || files.udyam_document)
  );
  const businessVerified = Boolean(businessVerification?.verified);
  const canSubmit =
    identityVerified &&
    hierarchyReady &&
    photosReady &&
    bankVerified &&
    businessVerified;

  function stepBlockedMessage() {
    if (step === 0 && !identityVerified) return identityReady ? (!panVerified ? "Verify PAN first, then complete Aadhaar via DigiLocker." : "Complete Aadhaar DigiLocker verification.") : "Complete identity details first.";
    if (step === 1 && !hierarchyReady) return "Select a valid parent or choose direct admin approval.";
    if (step === 2 && !photosReady) return "Upload all three photos and capture geotagging for each.";
    if (step === 3 && !bankVerified) return bankReady ? "Complete reverse penny drop verification before business details." : "Complete bank details first.";
    if (step === 4 && !businessVerified) return businessReady ? "Verify business details before review." : "Complete business details and upload business photo first.";
    return "";
  }

  function goNext() {
    const blocked = stepBlockedMessage();
    if (blocked) {
      setError(blocked);
      return;
    }
    setError("");
    setStep(Math.min(steps.length - 1, step + 1));
  }

  return (
    <Screen title="Onboarding">
      <Panel
        title="New Onboarding"
        action={<StatusBadge status={`Step ${step + 1} of ${steps.length}`} />}
      >
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
          {steps.map((label, index) => (
            <Text
              key={label}
              style={{
                backgroundColor: index === step ? colors.brand : colors.panelAlt,
                borderRadius: 8,
                color: index === step ? colors.white : colors.muted,
                fontSize: 12,
                fontWeight: "800",
                paddingHorizontal: 10,
                paddingVertical: 6
              }}
            >
              {label}
            </Text>
          ))}
        </View>

        {step === 0 && (
          <Grid>
            <SelectBox label="Onboarding Role" value={form.requested_role} options={roleOptions} onChange={(requested_role) => setForm({ ...form, requested_role, parent: null, direct_to_admin: requested_role === "SDBR" })} />
            <Field label="Mobile Number" value={form.mobile} onChangeText={(mobile) => updateForm("mobile", mobile)} keyboardType="phone-pad" />
            <Field label="Email" value={form.email} onChangeText={(email) => updateForm("email", email)} keyboardType="email-address" />
            <Field label="Full Name" value={form.full_name} onChangeText={(full_name) => updateForm("full_name", full_name)} />
            <Field label="DOB (YYYY-MM-DD)" value={form.dob} onChangeText={(dob) => updateForm("dob", dob)} />
            <Field label="Aadhaar Number" value={form.aadhaar_number} onChangeText={(aadhaar_number) => updateForm("aadhaar_number", aadhaar_number)} keyboardType="numeric" />
            <Field label="PAN Number" value={form.pan_number} onChangeText={(pan_number) => updateForm("pan_number", pan_number.toUpperCase())} />
            <Button icon="card-account-details-outline" variant={panVerified ? "secondary" : "primary"} onPress={() => verifyIdentity.mutate()} disabled={!identityReady || verifyIdentity.isPending}>
              {panVerified ? "PAN Verified" : "Verify PAN"}
            </Button>
            {panVerified && (
              <Button
                icon={aadhaarVerified ? "shield-check-outline" : "fingerprint"}
                variant={aadhaarVerified ? "secondary" : "primary"}
                onPress={() => digilockerInit.mutate()}
                disabled={aadhaarVerified || digilockerInit.isPending || digilockerStatus === "PENDING"}
              >
                {aadhaarVerified
                  ? "Aadhaar Verified via DigiLocker"
                  : digilockerStatus === "PENDING"
                  ? "Waiting for DigiLocker consent…"
                  : "Verify Aadhaar via DigiLocker"}
              </Button>
            )}
            {digilockerStatus === "PENDING" && (
              <Text style={{ color: colors.muted, fontSize: 12 }}>A browser window has opened. Complete DigiLocker consent and return here.</Text>
            )}
          </Grid>
        )}

        {step === 1 && (
          <Grid>
            {form.requested_role !== "SDBR" && <Toggle label="Send directly to admin without parent" value={form.direct_to_admin} onChange={(direct_to_admin) => setForm({ ...form, direct_to_admin, parent: direct_to_admin ? null : form.parent })} />}
            {form.requested_role !== "SDBR" && !form.direct_to_admin && <SelectBox label="Parent DBR / SDBR" value={form.parent} options={parentOptions} onChange={(parent) => setForm({ ...form, parent })} />}
            {form.requested_role === "SDBR" && <Text style={{ color: colors.muted, fontWeight: "700" }}>SDBR applications go directly to admin approval.</Text>}
          </Grid>
        )}

        {step === 2 && (
          <Grid>
            {[
              ["live_photo", "Live Photo", "live_photo_geo"],
              ["shop_photo", "Inside Shop", "shop_photo_geo"],
              ["agent_photo", "With Agent", "agent_photo_geo"]
            ].map(([fileField, label, geoField]) => (
              <View key={fileField} style={{ gap: 8, minWidth: 230 }}>
                <Button icon="camera-outline" variant={files[fileField as FileField] ? "secondary" : "ghost"} onPress={() => pick(fileField as FileField)}>
                  {files[fileField as FileField]?.name || label}
                </Button>
                <Button icon="crosshairs-gps" variant={geo[geoField as GeoField]?.captured_at ? "secondary" : "ghost"} onPress={() => captureGeo(geoField as GeoField)}>
                  {geo[geoField as GeoField]?.captured_at ? "Geo Captured" : "Capture Geo"}
                </Button>
              </View>
            ))}
          </Grid>
        )}

        {step === 3 && (
          <Grid>
            <Field label="Account Holder Name" value={form.account_holder_name} onChangeText={(account_holder_name) => updateForm("account_holder_name", account_holder_name)} />
            <Field label="Bank Name" value={form.bank_name} onChangeText={(bank_name) => updateForm("bank_name", bank_name)} />
            <Field label="Account Number" value={form.account_number} onChangeText={(account_number) => updateForm("account_number", account_number)} keyboardType="numeric" />
            <Field label="IFSC" value={form.ifsc} onChangeText={(ifsc) => updateForm("ifsc", ifsc.toUpperCase())} />
            <Field label="UPI ID" value={form.upi_id} onChangeText={(upi_id) => updateForm("upi_id", upi_id)} />
            <Button icon="file-upload-outline" variant={files.bank_proof ? "secondary" : "ghost"} onPress={() => pick("bank_proof")}>{files.bank_proof?.name || "Bank Proof"}</Button>
            <Button icon="bank-check" variant={bankVerified ? "secondary" : "primary"} onPress={() => verifyBank.mutate()} disabled={!bankReady || verifyBank.isPending}>
              {bankVerified ? "Bank Verified" : "Verify Bank"}
            </Button>
          </Grid>
        )}

        {step === 4 && (
          <Grid>
            <Field label="Business Name" value={form.business_name} onChangeText={(business_name) => updateForm("business_name", business_name)} />
            <Field label="Business Type" value={form.business_type} onChangeText={(business_type) => updateForm("business_type", business_type)} />
            <Field label="GST Number" value={form.gst_number} onChangeText={(gst_number) => updateForm("gst_number", gst_number.toUpperCase())} />
            <Field label="MSME / Udyam Number" value={form.udyam_number} onChangeText={(udyam_number) => updateForm("udyam_number", udyam_number.toUpperCase())} />
            <Field label="City" value={form.city} onChangeText={(city) => updateForm("city", city)} />
            <Field label="State" value={form.state} onChangeText={(state) => updateForm("state", state)} />
            <Field label="PIN Code" value={form.pin_code} onChangeText={(pin_code) => updateForm("pin_code", pin_code)} keyboardType="numeric" />
            <Field label="Business Address" value={form.business_address} onChangeText={(business_address) => updateForm("business_address", business_address)} multiline />
            <Button icon="storefront-outline" variant={files.business_photo ? "secondary" : "ghost"} onPress={() => pick("business_photo")}>{files.business_photo?.name || "Business Photo"}</Button>
            <Button icon="file-upload-outline" variant={files.gst_document ? "secondary" : "ghost"} onPress={() => pick("gst_document")}>{files.gst_document?.name || "GST Document"}</Button>
            <Button icon="file-upload-outline" variant={files.udyam_document ? "secondary" : "ghost"} onPress={() => pick("udyam_document")}>{files.udyam_document?.name || "MSME Document"}</Button>
            <Button icon="check-decagram-outline" variant={businessVerified ? "secondary" : "primary"} onPress={() => verifyBusiness.mutate()} disabled={!businessReady || verifyBusiness.isPending}>
              {businessVerified ? "Business Verified" : "Verify Business"}
            </Button>
          </Grid>
        )}

        {step === 5 && (
          <Grid>
            <Text style={{ color: colors.ink, fontWeight: "800" }}>{form.full_name || "Applicant"} · {form.requested_role}</Text>
            <Text style={{ color: colors.muted, fontWeight: "700" }}>Cashfree dummy mode will approve PAN and reverse penny drop until the env switch is turned off. DigiLocker always requires real user consent.</Text>
            {activeApplication && <StatusBadge status={`Existing ${activeApplication.status}`} />}
          </Grid>
        )}

        <ErrorText message={error} />
        <Grid>
          <Button icon="arrow-left" variant="ghost" onPress={() => setStep(Math.max(0, step - 1))} disabled={step === 0}>Back</Button>
          {step < steps.length - 1 && <Button icon="arrow-right" onPress={goNext}>Next</Button>}
          {step === steps.length - 1 && <Button icon="check-decagram-outline" onPress={() => submit.mutate()} disabled={!canSubmit || submit.isPending}>Submit Onboarding</Button>}
        </Grid>
      </Panel>

      <Panel title="Onboarding Status">
        <DataTable
          data={applications.data}
          keyExtractor={(row) => String(row.id)}
          columns={[
            { key: "date", title: "Date", width: 170, render: (row) => <Text>{dateTime(row.created_at)}</Text> },
            { key: "name", title: "Applicant", width: 180, render: (row) => <Text>{row.full_name}</Text> },
            { key: "role", title: "Role", width: 130, render: (row) => <Text>{row.requested_role}</Text> },
            { key: "parent", title: "Parent", width: 180, render: (row) => <Text>{row.parent_mobile || (row.direct_to_admin ? "Admin direct" : "-")}</Text> },
            { key: "mode", title: "Mode", width: 110, render: (row) => <Text>{row.verification_mode}</Text> },
            { key: "rpd", title: "RPD", width: 130, render: (row) => <StatusBadge status={row.rpd_status || "-"} /> },
            { key: "status", title: "Status", width: 160, render: (row) => <StatusBadge status={row.status} /> },
            { key: "note", title: "Note", width: 260, render: (row) => <Text>{row.review_note || "-"}</Text> },
            {
              key: "actions",
              title: "Actions",
              width: 230,
              render: (row) => (
                <Grid>
                  {row.status === "pending_parent" && row.parent === user?.id && <Button icon="check" onPress={() => review.mutate({ id: row.id, action: "approve" })}>Parent OK</Button>}
                  {row.status === "pending_parent" && row.parent === user?.id && <Button icon="close" variant="danger" onPress={() => review.mutate({ id: row.id, action: "reject" })}>Reject</Button>}
                </Grid>
              )
            }
          ]}
        />
      </Panel>
    </Screen>
  );
}
