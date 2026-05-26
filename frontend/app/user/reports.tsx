import { useQuery } from "@tanstack/react-query";
import React, { useState } from "react";
import { Text, View } from "react-native";

import { api } from "@/api/client";
import { Button, DataTable, EmptyState, Field, Grid, Panel, Screen, SelectBox, StatCard, StatusBadge } from "@/components/ui";
import type { Service } from "@/types";
import { dateTime, money } from "@/utils/format";

// ─── Filter bar for transactions ─────────────────────────────────────────────

function useTransactionFilters() {
  const [fromDate, setFromDate]   = useState("");
  const [toDate, setToDate]       = useState("");
  const [status, setStatus]       = useState("");
  const [serviceCode, setServiceCode] = useState("");
  const [applied, setApplied]     = useState<Record<string, string>>({});

  const applyFilters = () => {
    const q: Record<string, string> = {};
    if (fromDate) q["created_at__gte"] = `${fromDate}T00:00:00`;
    if (toDate)   q["created_at__lte"] = `${toDate}T23:59:59`;
    if (status)   q["status"] = status;
    if (serviceCode) q["service__code"] = serviceCode;
    setApplied(q);
  };

  const clearFilters = () => {
    setFromDate("");
    setToDate("");
    setStatus("");
    setServiceCode("");
    setApplied({});
  };

  return {
    fromDate, setFromDate,
    toDate, setToDate,
    status, setStatus,
    serviceCode, setServiceCode,
    applied,
    applyFilters,
    clearFilters,
  };
}

const TX_STATUS_OPTIONS = [
  { label: "All Statuses", value: "" },
  { label: "Success",      value: "success" },
  { label: "Pending",      value: "pending" },
  { label: "Failed",       value: "failed" },
  { label: "Quoted",       value: "quoted" },
  { label: "Refunded",     value: "refunded" },
  { label: "Reversed",     value: "reversed" },
  { label: "Manual Review",value: "manual_review" },
];

export default function UserReports() {
  const filters = useTransactionFilters();

  const services = useQuery({
    queryKey: ["services"],
    queryFn: () => api.services({ active: true }),
  });

  const transactions = useQuery({
    queryKey: ["transactions", filters.applied],
    queryFn: () => api.transactions(filters.applied),
  });

  const ledger = useQuery({
    queryKey: ["wallet-ledger"],
    queryFn: () => api.ledger(),
  });

  const commission = useQuery({
    queryKey: ["commission-ledger"],
    queryFn: api.commissionLedger,
  });

  // Summary counts from the transaction list
  const txData = transactions.data ?? [];
  const successCount = txData.filter((t) => t.status === "success").length;
  const pendingCount = txData.filter((t) => t.status === "pending").length;
  const failedCount  = txData.filter((t) => t.status === "failed" || t.status === "reversed" || t.status === "refunded").length;

  const serviceOptions = [
    { label: "All Services", value: "" },
    ...(services.data ?? []).map((s: Service) => ({ label: s.name, value: s.code })),
  ];

  return (
    <Screen title="Reports">
      {/* ── Transaction Summary ── */}
      <Grid>
        <StatCard label="Transactions" value={txData.length}  icon="swap-horizontal" tone="brand" />
        <StatCard label="Success"      value={successCount}   icon="check-circle-outline" tone="green" />
        <StatCard label="Pending"      value={pendingCount}   icon="clock-outline" tone="amber" />
        <StatCard label="Failed"       value={failedCount}    icon="close-circle-outline" tone="red" />
      </Grid>

      {/* ── Filters ── */}
      <Panel title="Filter Transactions">
        <Grid>
          <Field
            label="From Date (YYYY-MM-DD)"
            value={filters.fromDate}
            onChangeText={filters.setFromDate}
            placeholder="2026-01-01"
          />
          <Field
            label="To Date (YYYY-MM-DD)"
            value={filters.toDate}
            onChangeText={filters.setToDate}
            placeholder="2026-12-31"
          />
          <SelectBox
            label="Status"
            value={filters.status}
            options={TX_STATUS_OPTIONS}
            onChange={filters.setStatus}
          />
          <SelectBox
            label="Service"
            value={filters.serviceCode}
            options={serviceOptions}
            onChange={filters.setServiceCode}
          />
        </Grid>
        <Grid>
          <Button icon="filter-outline" onPress={filters.applyFilters}>Apply Filters</Button>
          <Button icon="filter-off-outline" variant="ghost" onPress={filters.clearFilters}>Clear</Button>
        </Grid>
      </Panel>

      {/* ── Transaction Report ── */}
      <Panel title="Transaction Report">
        {transactions.isLoading ? (
          <View style={{ padding: 16 }}>
            <Text style={{ textAlign: "center" }}>Loading transactions…</Text>
          </View>
        ) : txData.length === 0 ? (
          <EmptyState title="No transactions found for the selected filters." />
        ) : (
          <DataTable
            data={txData}
            keyExtractor={(row) => row.reference}
            columns={[
              { key: "ref",      title: "Reference",    width: 190, render: (row) => <Text selectable>{row.reference}</Text> },
              { key: "service",  title: "Service",      width: 190, render: (row) => <Text>{row.service_name ?? "—"}</Text> },
              { key: "operator", title: "Operator",     width: 160, render: (row) => <Text>{row.operator_name ?? "—"}</Text> },
              { key: "mobile",   title: "Customer",     width: 150, render: (row) => <Text>{row.customer_mobile || "—"}</Text> },
              { key: "amount",   title: "Amount",       width: 130, render: (row) => <Text>{money(row.amount)}</Text> },
              { key: "charge",   title: "Charge",       width: 110, render: (row) => <Text>{money(row.charge)}</Text> },
              { key: "comm",     title: "Commission",   width: 130, render: (row) => <Text>{money(row.commission)}</Text> },
              { key: "debit",    title: "Total Debit",  width: 130, render: (row) => <Text>{money(row.total_debit)}</Text> },
              { key: "pref",     title: "Provider Ref", width: 200, render: (row) => <Text selectable>{row.provider_reference || "N/A"}</Text> },
              { key: "status",   title: "Status",       width: 130, render: (row) => <StatusBadge status={row.status} /> },
              { key: "date",     title: "Date",         width: 190, render: (row) => <Text>{dateTime(row.created_at)}</Text> },
            ]}
          />
        )}
      </Panel>

      {/* ── Wallet Ledger ── */}
      <Panel title="Wallet Ledger">
        <DataTable
          data={ledger.data}
          keyExtractor={(row) => String(row.id)}
          columns={[
            { key: "type",    title: "Type",          width: 160, render: (row) => <Text>{row.entry_type}</Text> },
            { key: "ref",     title: "Reference",     width: 180, render: (row) => <Text selectable>{row.transaction_ref}</Text> },
            { key: "service", title: "Service",       width: 160, render: (row) => <Text>{row.service_name ?? "—"}</Text> },
            { key: "opening", title: "Opening (₹)",  width: 130, render: (row) => <Text>{money(row.opening_balance)}</Text> },
            { key: "amount",  title: "Amount (₹)",   width: 130, render: (row) => <Text>{money(row.amount)}</Text> },
            { key: "closing", title: "Closing (₹)",  width: 130, render: (row) => <Text>{money(row.closing_balance)}</Text> },
            { key: "remarks", title: "Remarks",      width: 200, render: (row) => <Text>{row.remarks}</Text> },
            { key: "date",    title: "Date",          width: 190, render: (row) => <Text>{dateTime(row.created_at)}</Text> },
          ]}
        />
      </Panel>

      {/* ── Commission Ledger ── */}
      <Panel title="Commission Ledger">
        <DataTable
          data={commission.data}
          keyExtractor={(row) => String(row.id)}
          columns={[
            { key: "ref",     title: "Transaction",  width: 190, render: (row) => <Text selectable>{row.transaction_reference ?? "—"}</Text> },
            { key: "service", title: "Service",      width: 190, render: (row) => <Text>{row.service_name ?? "—"}</Text> },
            { key: "amount",  title: "Amount (₹)",  width: 130, render: (row) => <Text>{money(row.amount)}</Text> },
            { key: "type",    title: "Type",         width: 170, render: (row) => <Text>{row.entry_type}</Text> },
            { key: "remarks", title: "Remarks",      width: 200, render: (row) => <Text>{row.remarks}</Text> },
            { key: "date",    title: "Date",         width: 190, render: (row) => <Text>{dateTime(row.created_at)}</Text> },
          ]}
        />
      </Panel>
    </Screen>
  );
}
