import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import React, { useEffect, useState } from "react";
import { Text } from "react-native";

import { api } from "@/api/client";
import { Button, DataTable, ErrorText, Field, Grid, LoadingState, Panel, Screen, StatusBadge } from "@/components/ui";
import { dateTime } from "@/utils/format";

export default function UserApiSettings() {
  const queryClient = useQueryClient();
  const setting = useQuery({ queryKey: ["partner-api-mine"], queryFn: api.partnerApiMine });
  const [apiKey, setApiKey] = useState("");
  const [allowedIp, setAllowedIp] = useState("");
  const [allowedIp2, setAllowedIp2] = useState("");
  const [webhookUrl, setWebhookUrl] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (setting.data) {
      setApiKey(setting.data.api_key || "");
      setAllowedIp(setting.data.allowed_ip || "");
      setAllowedIp2(setting.data.allowed_ip2 || "");
      setWebhookUrl(setting.data.webhook_url || "");
    }
  }, [setting.data]);

  const canEditApiKey = Boolean(setting.data?.api_key_editable);
  const isDummyMode = Boolean(setting.data?.dummy_mode);

  const save = useMutation({
    mutationFn: () =>
      api.updatePartnerApiMine({
        api_key: canEditApiKey ? apiKey.trim() : undefined,
        allowed_ip: allowedIp || null,
        allowed_ip2: allowedIp2 || null,
        webhook_url: webhookUrl
      }),
    onSuccess: () => {
      setError("");
      queryClient.invalidateQueries({ queryKey: ["partner-api-mine"] });
    },
    onError: (err) => setError(err instanceof Error ? err.message : "API settings update failed.")
  });

  const rotate = useMutation({
    mutationFn: api.rotatePartnerApiKey,
    onSuccess: () => {
      setError("");
      queryClient.invalidateQueries({ queryKey: ["partner-api-mine"] });
    },
    onError: (err) => setError(err instanceof Error ? err.message : "API key rotation failed.")
  });

  if (setting.isLoading) {
    return (
      <Screen title="API Settings">
        <LoadingState />
      </Screen>
    );
  }

  return (
    <Screen title="API Settings">
      <Panel title="Partner Credentials">
        <DataTable
          data={setting.data ? [setting.data] : []}
          keyExtractor={(row) => String(row.id)}
          columns={[
            { key: "key", title: "API Key", width: 390, render: (row) => <Text selectable>{row.api_key}</Text> },
            { key: "ip", title: "Primary IP", width: 150, render: (row) => <Text>{row.allowed_ip || "Any"}</Text> },
            { key: "ip2", title: "Secondary IP", width: 150, render: (row) => <Text>{row.allowed_ip2 || "Any"}</Text> },
            { key: "status", title: "Status", width: 120, render: (row) => <StatusBadge status={row.active ? "active" : "inactive"} /> },
            { key: "generated", title: "Generated", width: 190, render: (row) => <Text>{dateTime(row.generated_at)}</Text> }
          ]}
        />
        {canEditApiKey ? <Field label="Partner API Key" value={apiKey} onChangeText={setApiKey} placeholder="Enter the real partner API key" /> : null}
        <Text>{isDummyMode ? "Dummy partner key mode is enabled. Turn off PARTNER_API_DUMMY_MODE to use the real partner API key." : "Real partner key mode is enabled. Save the actual partner API key below when needed."}</Text>
        <Button icon="key-change" variant="danger" onPress={() => rotate.mutate()} disabled={rotate.isPending || isDummyMode}>Rotate API Key</Button>
      </Panel>

      <Panel title="Whitelist and Webhook">
        <Grid>
          <Field label="Allowed IP" value={allowedIp} onChangeText={setAllowedIp} placeholder="Leave blank to allow any IP" />
          <Field label="Allowed IP 2" value={allowedIp2} onChangeText={setAllowedIp2} placeholder="Optional fallback IP" />
          <Field label="Webhook URL" value={webhookUrl} onChangeText={setWebhookUrl} placeholder="https://partner.example.com/callback" />
        </Grid>
        <ErrorText message={error} />
        <Button icon="content-save-outline" onPress={() => save.mutate()} disabled={save.isPending}>Save API Settings</Button>
      </Panel>
    </Screen>
  );
}
