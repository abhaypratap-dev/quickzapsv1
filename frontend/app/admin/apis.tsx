import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import React, { useState } from "react";
import { Text } from "react-native";

import { api } from "@/api/client";
import { Button, DataTable, Field, Grid, Panel, Screen, SelectBox, StatusBadge } from "@/components/ui";
import type { ID } from "@/types";

export default function AdminApis() {
  const queryClient = useQueryClient();
  const [service, setService] = useState<ID | null>(null);
  const [operator, setOperator] = useState<ID | null>(null);
  const [provider, setProvider] = useState<ID | null>(null);
  const [marginValue, setMarginValue] = useState("0.3");
  const [marginType, setMarginType] = useState<"fixed" | "percent">("percent");

  const services = useQuery({ queryKey: ["services"], queryFn: () => api.services() });
  const operators = useQuery({ queryKey: ["operators", service], queryFn: () => api.operators({ service: service || "" }) });
  const providers = useQuery({ queryKey: ["providers"], queryFn: () => api.providers() });
  const margins = useQuery({ queryKey: ["api-margins"], queryFn: () => api.apiMargins() });

  const save = useMutation({
    mutationFn: () => api.saveApiMargin({ service, operator, provider, margin_value: marginValue, margin_type: marginType, active: true }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["api-margins"] })
  });

  return (
    <Screen title="APIs">
      <Panel title="Admin API Margin">
        <Grid>
          <SelectBox label="Service" value={service} options={[{ label: "Select", value: null }, ...(services.data || []).map((item) => ({ label: item.name, value: item.id }))]} onChange={setService} />
          <SelectBox label="Operator" value={operator} options={[{ label: "Any operator", value: null }, ...(operators.data || []).map((item) => ({ label: item.name, value: item.id }))]} onChange={setOperator} />
          <SelectBox label="API Provider" value={provider} options={[{ label: "Select", value: null }, ...(providers.data || []).map((item) => ({ label: item.name, value: item.id }))]} onChange={setProvider} />
          <Field label="Admin Margin" value={marginValue} onChangeText={setMarginValue} keyboardType="numeric" />
          <SelectBox
            label="Margin Type"
            value={marginType}
            options={[
              { label: "Percent", value: "percent" },
              { label: "Fixed", value: "fixed" }
            ]}
            onChange={setMarginType}
          />
        </Grid>
        <Button icon="content-save-outline" onPress={() => save.mutate()} disabled={!service || !provider}>Save Margin</Button>
        <DataTable
          data={margins.data}
          keyExtractor={(row) => String(row.id)}
          columns={[
            { key: "service", title: "Service", width: 180, render: (row) => <Text>{row.service_name}</Text> },
            { key: "operator", title: "Operator", width: 160, render: (row) => <Text>{row.operator_name || "Any"}</Text> },
            { key: "provider", title: "API Provider", width: 190, render: (row) => <Text>{row.provider_name}</Text> },
            { key: "margin", title: "Margin", width: 140, render: (row) => <Text>{row.margin_value} {row.margin_type}</Text> },
            { key: "status", title: "Status", width: 120, render: (row) => <StatusBadge status={row.active ? "active" : "inactive"} /> }
          ]}
        />
      </Panel>

      <Panel title="Provider Configuration">
        <DataTable
          data={providers.data}
          keyExtractor={(row) => String(row.id)}
          columns={[
            { key: "code", title: "Code", width: 180, render: (row) => <Text>{row.code}</Text> },
            { key: "name", title: "Name", width: 220, render: (row) => <Text>{row.name}</Text> },
            { key: "type", title: "Type", width: 150, render: (row) => <Text>{row.provider_type}</Text> },
            { key: "health", title: "Health", width: 120, render: (row) => <StatusBadge status={row.health_status} /> },
            { key: "active", title: "Status", width: 120, render: (row) => <StatusBadge status={row.active ? "active" : "inactive"} /> }
          ]}
        />
      </Panel>
    </Screen>
  );
}
