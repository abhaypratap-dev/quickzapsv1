import { useQuery } from "@tanstack/react-query";
import React from "react";
import { Text, View } from "react-native";

import { api } from "@/api/client";
import { DataTable, Grid, LoadingState, Panel, Screen, StatCard, StatusBadge } from "@/components/ui";
import { dateTime, money, number } from "@/utils/format";

export default function AdminDashboard() {
  const dashboard = useQuery({ queryKey: ["dashboard"], queryFn: api.dashboard });

  if (dashboard.isLoading) {
    return (
      <Screen title="Dashboard">
        <LoadingState />
      </Screen>
    );
  }

  const data = dashboard.data;

  return (
    <Screen title="Dashboard">
      <Grid>
        <StatCard label="Success" value={number(data?.totals.success)} icon="check-circle-outline" tone="green" />
        <StatCard label="Failed" value={number(data?.totals.failed)} icon="close-circle-outline" tone="red" />
        <StatCard label="Pending" value={number(data?.totals.pending)} icon="clock-outline" tone="amber" />
        <StatCard label="Transactions" value={number(data?.totals.total_transactions)} icon="swap-horizontal" tone="brand" />
        <StatCard label="Amount" value={money(String(data?.totals.total_amount || 0))} icon="cash-multiple" tone="teal" />
        <StatCard label="Commission" value={money(String(data?.totals.total_commission || 0))} icon="percent-outline" tone="violet" />
        <StatCard label="Pending KYC" value={number(data?.pending_counts.kyc)} icon="card-account-details-outline" tone="cyan" />
        <StatCard label="Fund Requests" value={number(data?.pending_counts.fund_requests)} icon="bank-transfer-in" tone="amber" />
      </Grid>

      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 16 }}>
        <Panel title="Transaction Trend" style={{ flexGrow: 1, minWidth: 320 }}>
          <DataTable
            data={data?.trend || []}
            keyExtractor={(row, index) => `${row.month}-${index}`}
            columns={[
              { key: "month", title: "Month", width: 190, render: (row) => <Text>{row.month ? dateTime(String(row.month)) : "-"}</Text> },
              { key: "count", title: "Count", width: 120, render: (row) => <Text>{number(row.count as number)}</Text> },
              { key: "amount", title: "Amount", width: 160, render: (row) => <Text>{money(String(row.amount || 0))}</Text> }
            ]}
          />
        </Panel>
        <Panel title="Service Summary" style={{ flexGrow: 1, minWidth: 320 }}>
          <DataTable
            data={data?.service_summary || []}
            keyExtractor={(row, index) => `${row.service__name}-${row.status}-${index}`}
            columns={[
              { key: "service", title: "Service", width: 180, render: (row) => <Text>{String(row.service__name || "-")}</Text> },
              { key: "status", title: "Status", width: 120, render: (row) => <StatusBadge status={String(row.status || "")} /> },
              { key: "count", title: "Count", width: 100, render: (row) => <Text>{number(row.count as number)}</Text> },
              { key: "amount", title: "Amount", width: 150, render: (row) => <Text>{money(String(row.amount || 0))}</Text> }
            ]}
          />
        </Panel>
      </View>

      <Panel title="Last Transactions">
        <DataTable
          data={data?.last_transactions || []}
          keyExtractor={(row) => row.reference}
          columns={[
            { key: "ref", title: "Reference", width: 180, render: (row) => <Text>{row.reference}</Text> },
            { key: "user", title: "User", width: 180, render: (row) => <Text>{row.user_mobile}</Text> },
            { key: "service", title: "Service", width: 180, render: (row) => <Text>{row.service_name}</Text> },
            { key: "amount", title: "Amount", width: 130, render: (row) => <Text>{money(row.amount)}</Text> },
            { key: "status", title: "Status", width: 120, render: (row) => <StatusBadge status={row.status} /> },
            { key: "date", title: "Date", width: 190, render: (row) => <Text>{dateTime(row.created_at)}</Text> }
          ]}
        />
      </Panel>

      <Panel title="News">
        <DataTable
          data={data?.news || []}
          keyExtractor={(row) => String(row.id)}
          columns={[
            { key: "title", title: "Title", width: 220, render: (row) => <Text>{row.title}</Text> },
            { key: "body", title: "Message", width: 420, render: (row) => <Text>{row.body}</Text> },
            { key: "role", title: "Role", width: 160, render: (row) => <Text>{row.target_role_name || "All roles"}</Text> }
          ]}
        />
      </Panel>
    </Screen>
  );
}
