import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import React, { useEffect, useMemo, useState } from "react";
import { Text } from "react-native";

import { api } from "@/api/client";
import { Button, DataTable, Field, Grid, Panel, Screen, SelectBox, StatusBadge, Toggle } from "@/components/ui";
import type { ID } from "@/types";

export default function AdminSettings() {
  const queryClient = useQueryClient();
  const [newsTitle, setNewsTitle] = useState("");
  const [newsBody, setNewsBody] = useState("");
  const [newsRole, setNewsRole] = useState<ID | null>(null);
  const [packageName, setPackageName] = useState("");
  const [packageDescription, setPackageDescription] = useState("");
  const [bannerTitle, setBannerTitle] = useState("");
  const [bannerDescription, setBannerDescription] = useState("");
  const [showType, setShowType] = useState("dashboard");
  const [bulkChannel, setBulkChannel] = useState<"email" | "whatsapp" | "notification">("notification");
  const [bulkSubject, setBulkSubject] = useState("");
  const [bulkBody, setBulkBody] = useState("");
  const [bulkRole, setBulkRole] = useState<ID | null>(null);
  const [policyUser, setPolicyUser] = useState<ID | null>(null);
  const [policy, setPolicy] = useState({
    login_sms_otp_enabled: false,
    login_email_otp_enabled: false,
    login_whatsapp_otp_enabled: false,
    login_mpin_enabled: false,
    transaction_tpin_required: true,
    change_mpin_allowed: true,
    change_tpin_allowed: true,
    aadhaar_kyc_required: true,
    pan_kyc_required: true,
    cap_balance_enforced: false
  });

  const roles = useQuery({ queryKey: ["roles"], queryFn: () => api.roles() });
  const users = useQuery({ queryKey: ["users", "security"], queryFn: () => api.users({ status: "active" }) });
  const news = useQuery({ queryKey: ["news"], queryFn: () => api.news() });
  const packages = useQuery({ queryKey: ["service-packages"], queryFn: () => api.servicePackages() });
  const banners = useQuery({ queryKey: ["popup-banners"], queryFn: () => api.popupBanners() });
  const messages = useQuery({ queryKey: ["bulk-messages"], queryFn: () => api.bulkMessages() });

  const roleOptions = [{ label: "All roles", value: null as ID | null }, ...(roles.data || []).map((role) => ({ label: role.name, value: role.id }))];
  const userOptions = useMemo(() => [{ label: "Select", value: null as ID | null }, ...(users.data || []).map((user) => ({ label: `${user.mobile} ${user.role_name || ""}`, value: user.id }))], [users.data]);
  const selectedUser = useMemo(() => (users.data || []).find((user) => user.id === policyUser), [policyUser, users.data]);

  useEffect(() => {
    if (selectedUser?.security_policy) {
      setPolicy({
        login_sms_otp_enabled: selectedUser.security_policy.login_sms_otp_enabled,
        login_email_otp_enabled: selectedUser.security_policy.login_email_otp_enabled,
        login_whatsapp_otp_enabled: selectedUser.security_policy.login_whatsapp_otp_enabled,
        login_mpin_enabled: selectedUser.security_policy.login_mpin_enabled,
        transaction_tpin_required: selectedUser.security_policy.transaction_tpin_required,
        change_mpin_allowed: selectedUser.security_policy.change_mpin_allowed,
        change_tpin_allowed: selectedUser.security_policy.change_tpin_allowed,
        aadhaar_kyc_required: selectedUser.security_policy.aadhaar_kyc_required,
        pan_kyc_required: selectedUser.security_policy.pan_kyc_required,
        cap_balance_enforced: selectedUser.security_policy.cap_balance_enforced
      });
    }
  }, [selectedUser]);

  const createNews = useMutation({
    mutationFn: () => api.createNews({ title: newsTitle, body: newsBody, target_role: newsRole, active: true, priority: 5 }),
    onSuccess: () => {
      setNewsTitle("");
      setNewsBody("");
      queryClient.invalidateQueries({ queryKey: ["news"] });
    }
  });

  const createPackage = useMutation({
    mutationFn: () => api.createServicePackage({ name: packageName, description: packageDescription, active: true }),
    onSuccess: () => {
      setPackageName("");
      setPackageDescription("");
      queryClient.invalidateQueries({ queryKey: ["service-packages"] });
    }
  });

  const createBanner = useMutation({
    mutationFn: () => api.createPopupBanner({ title: bannerTitle, description: bannerDescription, show_type: showType, active: true }),
    onSuccess: () => {
      setBannerTitle("");
      setBannerDescription("");
      queryClient.invalidateQueries({ queryKey: ["popup-banners"] });
    }
  });

  const createMessage = useMutation({
    mutationFn: () => api.createBulkMessage({ channel: bulkChannel, target_role: bulkRole, subject: bulkSubject, body: bulkBody }),
    onSuccess: (message) => {
      setBulkSubject("");
      setBulkBody("");
      queryClient.invalidateQueries({ queryKey: ["bulk-messages"] });
      api.sendBulkMessage(message.id).then(() => queryClient.invalidateQueries({ queryKey: ["bulk-messages"] }));
    }
  });

  const savePolicy = useMutation({
    mutationFn: () => api.updateSecurityPolicy(policyUser as ID, policy),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] })
  });

  return (
    <Screen title="Settings">
      <Panel title="News Master">
        <Grid>
          <SelectBox label="Target Role" value={newsRole} options={roleOptions} onChange={setNewsRole} />
          <Field label="News Title" value={newsTitle} onChangeText={setNewsTitle} />
          <Field label="News Content" value={newsBody} onChangeText={setNewsBody} multiline />
        </Grid>
        <Button icon="newspaper-plus" onPress={() => createNews.mutate()} disabled={!newsTitle || !newsBody}>Submit News</Button>
        <DataTable
          data={news.data}
          keyExtractor={(row) => String(row.id)}
          columns={[
            { key: "title", title: "Title", width: 220, render: (row) => <Text>{row.title}</Text> },
            { key: "body", title: "Content", width: 360, render: (row) => <Text>{row.body}</Text> },
            { key: "role", title: "Role", width: 150, render: (row) => <Text>{row.target_role_name || "All roles"}</Text> },
            { key: "status", title: "Status", width: 120, render: (row) => <StatusBadge status={row.active ? "active" : "inactive"} /> }
          ]}
        />
      </Panel>

      <Panel title="Popup Banner">
        <Grid>
          <Field label="Banner Title" value={bannerTitle} onChangeText={setBannerTitle} />
          <SelectBox
            label="Show Type"
            value={showType}
            options={[
              { label: "Dashboard", value: "dashboard" },
              { label: "Login", value: "login" },
              { label: "Service", value: "service" },
              { label: "All", value: "all" }
            ]}
            onChange={setShowType}
          />
          <Field label="Description" value={bannerDescription} onChangeText={setBannerDescription} multiline />
        </Grid>
        <Button icon="image-plus" onPress={() => createBanner.mutate()} disabled={!bannerTitle}>Save Banner</Button>
        <DataTable
          data={banners.data}
          keyExtractor={(row) => String(row.id)}
          columns={[
            { key: "title", title: "Title", width: 220, render: (row) => <Text>{row.title}</Text> },
            { key: "show", title: "Show Type", width: 140, render: (row) => <Text>{row.show_type}</Text> },
            { key: "desc", title: "Description", width: 360, render: (row) => <Text>{row.description}</Text> },
            { key: "status", title: "Status", width: 120, render: (row) => <StatusBadge status={row.active ? "active" : "inactive"} /> }
          ]}
        />
      </Panel>

      <Panel title="Service Package">
        <Grid>
          <Field label="Package Name" value={packageName} onChangeText={setPackageName} />
          <Field label="Description" value={packageDescription} onChangeText={setPackageDescription} />
        </Grid>
        <Button icon="package-variant-plus" onPress={() => createPackage.mutate()} disabled={!packageName}>Create Package</Button>
        <DataTable
          data={packages.data}
          keyExtractor={(row) => String(row.id)}
          columns={[
            { key: "name", title: "Package", width: 220, render: (row) => <Text>{row.name}</Text> },
            { key: "desc", title: "Description", width: 360, render: (row) => <Text>{row.description}</Text> },
            { key: "status", title: "Status", width: 120, render: (row) => <StatusBadge status={row.active ? "active" : "inactive"} /> }
          ]}
        />
      </Panel>

      <Panel title="Send Bulk Message">
        <Grid>
          <SelectBox
            label="Channel"
            value={bulkChannel}
            options={[
              { label: "Notification", value: "notification" },
              { label: "Email", value: "email" },
              { label: "WhatsApp", value: "whatsapp" }
            ]}
            onChange={setBulkChannel}
          />
          <SelectBox label="User Type" value={bulkRole} options={roleOptions} onChange={setBulkRole} />
          <Field label="Subject" value={bulkSubject} onChangeText={setBulkSubject} />
          <Field label="Message Body" value={bulkBody} onChangeText={setBulkBody} multiline />
        </Grid>
        <Button icon="send-outline" onPress={() => createMessage.mutate()} disabled={!bulkBody}>Send</Button>
        <DataTable
          data={messages.data}
          keyExtractor={(row) => String(row.id)}
          columns={[
            { key: "channel", title: "Channel", width: 140, render: (row) => <Text>{row.channel}</Text> },
            { key: "subject", title: "Subject", width: 220, render: (row) => <Text>{row.subject || "-"}</Text> },
            { key: "role", title: "Role", width: 150, render: (row) => <Text>{row.target_role_name || "All roles"}</Text> },
            { key: "count", title: "Recipients", width: 120, render: (row) => <Text>{row.recipient_count}</Text> },
            { key: "status", title: "Status", width: 120, render: (row) => <StatusBadge status={row.status} /> }
          ]}
        />
      </Panel>

      <Panel title="OTP Permission">
        <Grid>
          <SelectBox label="User" value={policyUser} options={userOptions} onChange={setPolicyUser} />
          <Toggle label="Login SMS OTP" value={policy.login_sms_otp_enabled} onChange={(value) => setPolicy({ ...policy, login_sms_otp_enabled: value })} />
          <Toggle label="Login Email OTP" value={policy.login_email_otp_enabled} onChange={(value) => setPolicy({ ...policy, login_email_otp_enabled: value })} />
          <Toggle label="Login WhatsApp OTP" value={policy.login_whatsapp_otp_enabled} onChange={(value) => setPolicy({ ...policy, login_whatsapp_otp_enabled: value })} />
          <Toggle label="Login MPIN" value={policy.login_mpin_enabled} onChange={(value) => setPolicy({ ...policy, login_mpin_enabled: value })} />
          <Toggle label="Transaction TPIN" value={policy.transaction_tpin_required} onChange={(value) => setPolicy({ ...policy, transaction_tpin_required: value })} />
          <Toggle label="Change MPIN" value={policy.change_mpin_allowed} onChange={(value) => setPolicy({ ...policy, change_mpin_allowed: value })} />
          <Toggle label="Change TPIN" value={policy.change_tpin_allowed} onChange={(value) => setPolicy({ ...policy, change_tpin_allowed: value })} />
          <Toggle label="Aadhaar KYC" value={policy.aadhaar_kyc_required} onChange={(value) => setPolicy({ ...policy, aadhaar_kyc_required: value })} />
          <Toggle label="PAN KYC" value={policy.pan_kyc_required} onChange={(value) => setPolicy({ ...policy, pan_kyc_required: value })} />
          <Toggle label="Cap Balance" value={policy.cap_balance_enforced} onChange={(value) => setPolicy({ ...policy, cap_balance_enforced: value })} />
        </Grid>
        <Button icon="content-save-outline" onPress={() => savePolicy.mutate()} disabled={!policyUser}>Save Permission</Button>
      </Panel>
    </Screen>
  );
}
