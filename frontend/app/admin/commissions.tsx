import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import React, { useMemo, useState } from "react";
import { Text } from "react-native";

import { api } from "@/api/client";
import { Button, DataTable, ErrorText, Field, Grid, Panel, Screen, SelectBox, StatusBadge } from "@/components/ui";
import type { ID, Role } from "@/types";

export default function AdminCommissions() {
  const queryClient = useQueryClient();
  const [schemeRole, setSchemeRole] = useState<ID | null>(null);
  const [schemeName, setSchemeName] = useState("");
  const [schemeRemark, setSchemeRemark] = useState("");
  const [ruleScheme, setRuleScheme] = useState<ID | null>(null);
  const [ruleService, setRuleService] = useState<ID | null>(null);
  const [ruleOperator, setRuleOperator] = useState<ID | null>(null);
  const [commissionValue, setCommissionValue] = useState("0.5");
  const [commissionType, setCommissionType] = useState<"fixed" | "percent">("percent");
  const [surchargeValue, setSurchargeValue] = useState("1");
  const [surchargeType, setSurchargeType] = useState<"fixed" | "percent">("fixed");
  const [tdsPercent, setTdsPercent] = useState("5");
  const [gstPercent, setGstPercent] = useState("18");
  const [error, setError] = useState("");

  const roles = useQuery({ queryKey: ["roles"], queryFn: () => api.roles() });
  const schemes = useQuery({ queryKey: ["schemes"], queryFn: () => api.schemes() });
  const services = useQuery({ queryKey: ["services"], queryFn: () => api.services() });
  const operators = useQuery({ queryKey: ["operators", ruleService], queryFn: () => api.operators({ service: ruleService || "" }) });
  const rules = useQuery({ queryKey: ["commission-rules"], queryFn: () => api.commissionRules() });

  const roleOptions = useMemo(() => [{ label: "Select", value: null as ID | null }, ...(roles.data || []).map((role: Role) => ({ label: role.name, value: role.id }))], [roles.data]);
  const schemeOptions = [{ label: "Select", value: null as ID | null }, ...(schemes.data || []).map((scheme) => ({ label: scheme.name, value: scheme.id }))];
  const serviceOptions = [{ label: "Select", value: null as ID | null }, ...(services.data || []).map((service) => ({ label: service.name, value: service.id }))];
  const operatorOptions = [{ label: "Any operator", value: null as ID | null }, ...(operators.data || []).map((operator) => ({ label: operator.name, value: operator.id }))];

  const createScheme = useMutation({
    mutationFn: () => api.createScheme({ role: schemeRole, name: schemeName, remark: schemeRemark, active: true }),
    onSuccess: () => {
      setSchemeName("");
      setSchemeRemark("");
      setError("");
      queryClient.invalidateQueries({ queryKey: ["schemes"] });
    },
    onError: (err) => setError(err instanceof Error ? err.message : "Scheme creation failed.")
  });

  const saveRule = useMutation({
    mutationFn: () =>
      api.saveCommissionRule({
        scheme: ruleScheme,
        service: ruleService,
        operator: ruleOperator,
        commission_value: commissionValue,
        commission_type: commissionType,
        surcharge_value: surchargeValue,
        surcharge_type: surchargeType,
        tds_percent: tdsPercent,
        gst_percent: gstPercent,
        active: true
      }),
    onSuccess: () => {
      setError("");
      queryClient.invalidateQueries({ queryKey: ["commission-rules"] });
    },
    onError: (err) => setError(err instanceof Error ? err.message : "Commission rule save failed.")
  });

  return (
    <Screen title="Commission Setting">
      <Panel title="Scheme Master">
        <Grid>
          <SelectBox label="Role Type" value={schemeRole} options={roleOptions} onChange={setSchemeRole} />
          <Field label="Scheme Name" value={schemeName} onChangeText={setSchemeName} />
          <Field label="Remark" value={schemeRemark} onChangeText={setSchemeRemark} />
        </Grid>
        <ErrorText message={error} />
        <Button icon="playlist-plus" onPress={() => createScheme.mutate()} disabled={!schemeRole || !schemeName}>
          Create Scheme
        </Button>
      </Panel>

      <Panel title="Commission Setting">
        <Grid>
          <SelectBox label="Scheme" value={ruleScheme} options={schemeOptions} onChange={setRuleScheme} />
          <SelectBox label="Service" value={ruleService} options={serviceOptions} onChange={setRuleService} />
          <SelectBox label="Operator" value={ruleOperator} options={operatorOptions} onChange={setRuleOperator} />
          <Field label="Commission" value={commissionValue} onChangeText={setCommissionValue} keyboardType="numeric" />
          <SelectBox
            label="Commission Type"
            value={commissionType}
            options={[
              { label: "Percent", value: "percent" },
              { label: "Fixed", value: "fixed" }
            ]}
            onChange={setCommissionType}
          />
          <Field label="Surcharge" value={surchargeValue} onChangeText={setSurchargeValue} keyboardType="numeric" />
          <SelectBox
            label="Surcharge Type"
            value={surchargeType}
            options={[
              { label: "Fixed", value: "fixed" },
              { label: "Percent", value: "percent" }
            ]}
            onChange={setSurchargeType}
          />
          <Field label="TDS Percent" value={tdsPercent} onChangeText={setTdsPercent} keyboardType="numeric" />
          <Field label="GST Percent" value={gstPercent} onChangeText={setGstPercent} keyboardType="numeric" />
        </Grid>
        <Button icon="content-save-outline" onPress={() => saveRule.mutate()} disabled={!ruleScheme || !ruleService}>
          Save Rule
        </Button>
      </Panel>

      <Panel title="Commission Table">
        <DataTable
          data={rules.data}
          keyExtractor={(row) => String(row.id)}
          columns={[
            { key: "scheme", title: "Scheme", width: 190, render: (row) => <Text>{row.scheme_name}</Text> },
            { key: "service", title: "Service", width: 190, render: (row) => <Text>{row.service_name}</Text> },
            { key: "operator", title: "Operator", width: 160, render: (row) => <Text>{row.operator_name || "Any"}</Text> },
            { key: "comm", title: "Commission", width: 140, render: (row) => <Text>{row.commission_value} {row.commission_type}</Text> },
            { key: "surcharge", title: "Surcharge", width: 140, render: (row) => <Text>{row.surcharge_value} {row.surcharge_type}</Text> },
            { key: "tax", title: "TDS/GST", width: 130, render: (row) => <Text>{row.tds_percent}/{row.gst_percent}</Text> },
            { key: "status", title: "Status", width: 110, render: (row) => <StatusBadge status={row.active ? "active" : "inactive"} /> }
          ]}
        />
      </Panel>
    </Screen>
  );
}
