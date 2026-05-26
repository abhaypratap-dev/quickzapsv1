import { useQuery } from "@tanstack/react-query";
import React from "react";
import { Text } from "react-native";

import { api } from "@/api/client";
import { DataTable, Grid, LoadingState, Panel, Screen, StatCard, StatusBadge } from "@/components/ui";
import { useAuth } from "@/context/AuthContext";
import { dateTime, money, number } from "@/utils/format";

export default function UserDashboard() {
  const { user } = useAuth();
  const dashboard = useQuery({ queryKey: ["dashboard"], queryFn: api.dashboard });
  const wallet = useQuery({ queryKey: ["wallet-mine"], queryFn: api.walletMine });

  if (dashboard.isLoading || wallet.isLoading) {
    return (
      <Screen title="Dashboard">
        <LoadingState />
      </Screen>
    );
  }

  return (
    <Screen title="Dashboard">
      <Grid>
        <StatCard label="Available Balance" value={money(wallet.data?.available_balance)} icon="wallet-outline" tone="green" />
        <StatCard label="Hold Balance" value={money(wallet.data?.hold_balance)} icon="lock-clock" tone="amber" />
        <StatCard label="Successful Transactions" value={number(dashboard.data?.totals.success)} icon="check-circle-outline" tone="teal" />
        <StatCard label="Pending Transactions" value={number(dashboard.data?.totals.pending)} icon="clock-outline" tone="amber" />
        <StatCard label="Commission" value={money(String(dashboard.data?.totals.total_commission || 0))} icon="percent-outline" tone="violet" />
        <StatCard label="KYC Status" value={user?.kyc_status || "-"} icon="card-account-details-outline" tone="cyan" />
      </Grid>

      <Panel title="Last Transactions">
        <DataTable
          data={dashboard.data?.last_transactions || []}
          keyExtractor={(row) => row.reference}
          columns={[
            { key: "ref", title: "Reference", width: 180, render: (row) => <Text>{row.reference}</Text> },
            { key: "service", title: "Service", width: 190, render: (row) => <Text>{row.service_name}</Text> },
            { key: "amount", title: "Amount", width: 130, render: (row) => <Text>{money(row.amount)}</Text> },
            { key: "debit", title: "Debit", width: 130, render: (row) => <Text>{money(row.total_debit)}</Text> },
            { key: "commission", title: "Commission", width: 140, render: (row) => <Text>{money(row.commission)}</Text> },
            { key: "status", title: "Status", width: 130, render: (row) => <StatusBadge status={row.status} /> },
            { key: "date", title: "Date", width: 190, render: (row) => <Text>{dateTime(row.created_at)}</Text> }
          ]}
        />
      </Panel>

      <Panel title="News">
        <DataTable
          data={dashboard.data?.news || []}
          keyExtractor={(row) => String(row.id)}
          columns={[
            { key: "title", title: "Title", width: 220, render: (row) => <Text>{row.title}</Text> },
            { key: "body", title: "Message", width: 420, render: (row) => <Text>{row.body}</Text> }
          ]}
        />
      </Panel>
    </Screen>
  );
}
