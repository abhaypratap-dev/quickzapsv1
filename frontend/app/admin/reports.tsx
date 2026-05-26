import { useQuery } from "@tanstack/react-query";
import React from "react";
import { Text } from "react-native";

import { api } from "@/api/client";
import { DataTable, Panel, Screen, StatusBadge } from "@/components/ui";
import { dateTime, money } from "@/utils/format";

export default function AdminReports() {
  const transactions = useQuery({ queryKey: ["transactions"], queryFn: () => api.transactions() });
  const ledger = useQuery({ queryKey: ["report-ledger"], queryFn: api.reportLedger });
  const commission = useQuery({ queryKey: ["commission-ledger"], queryFn: api.commissionLedger });
  const walletSummary = useQuery({ queryKey: ["wallet-summary"], queryFn: api.walletSummary });

  return (
    <Screen title="Reports">
      <Panel title="Recharge / DMT / Express Money / Account Verification Reports">
        <DataTable
          data={transactions.data}
          keyExtractor={(row) => row.reference}
          columns={[
            { key: "ref", title: "Reference", width: 180, render: (row) => <Text>{row.reference}</Text> },
            { key: "user", title: "User", width: 150, render: (row) => <Text>{row.user_mobile}</Text> },
            { key: "service", title: "Service", width: 180, render: (row) => <Text>{row.service_name}</Text> },
            { key: "provider", title: "Provider", width: 180, render: (row) => <Text>{row.provider_name}</Text> },
            { key: "amount", title: "Amount", width: 130, render: (row) => <Text>{money(row.amount)}</Text> },
            { key: "charge", title: "Charge", width: 130, render: (row) => <Text>{money(row.charge)}</Text> },
            { key: "commission", title: "Commission", width: 140, render: (row) => <Text>{money(row.commission)}</Text> },
            { key: "status", title: "Status", width: 130, render: (row) => <StatusBadge status={row.status} /> },
            { key: "date", title: "Date", width: 190, render: (row) => <Text>{dateTime(row.created_at)}</Text> }
          ]}
        />
      </Panel>

      <Panel title="Admin Ledger Report">
        <DataTable
          data={ledger.data}
          keyExtractor={(row) => String(row.id)}
          columns={[
            { key: "user", title: "User", width: 150, render: (row) => <Text>{row.user_mobile}</Text> },
            { key: "type", title: "Type", width: 160, render: (row) => <Text>{row.entry_type}</Text> },
            { key: "ref", title: "Reference", width: 180, render: (row) => <Text>{row.transaction_ref}</Text> },
            { key: "opening", title: "Opening", width: 130, render: (row) => <Text>{money(row.opening_balance)}</Text> },
            { key: "amount", title: "Amount", width: 130, render: (row) => <Text>{money(row.amount)}</Text> },
            { key: "closing", title: "Closing", width: 130, render: (row) => <Text>{money(row.closing_balance)}</Text> },
            { key: "remarks", title: "Remarks", width: 260, render: (row) => <Text>{row.remarks}</Text> }
          ]}
        />
      </Panel>

      <Panel title="Admin Commission Ledger">
        <DataTable
          data={commission.data}
          keyExtractor={(row) => String(row.id)}
          columns={[
            { key: "user", title: "User", width: 150, render: (row) => <Text>{row.user_mobile}</Text> },
            { key: "ref", title: "Transaction", width: 180, render: (row) => <Text>{row.transaction_reference}</Text> },
            { key: "service", title: "Service", width: 180, render: (row) => <Text>{row.service_name}</Text> },
            { key: "amount", title: "Amount", width: 130, render: (row) => <Text>{money(row.amount)}</Text> },
            { key: "type", title: "Type", width: 170, render: (row) => <Text>{row.entry_type}</Text> },
            { key: "date", title: "Date", width: 190, render: (row) => <Text>{dateTime(row.created_at)}</Text> }
          ]}
        />
      </Panel>

      <Panel title="Wallet Summary">
        <DataTable
          data={walletSummary.data}
          keyExtractor={(row) => String(row.id)}
          columns={[
            { key: "user", title: "User", width: 150, render: (row) => <Text>{row.user_mobile}</Text> },
            { key: "name", title: "Name", width: 180, render: (row) => <Text>{row.user_name}</Text> },
            { key: "available", title: "Available", width: 150, render: (row) => <Text>{money(row.available_balance)}</Text> },
            { key: "hold", title: "Hold", width: 130, render: (row) => <Text>{money(row.hold_balance)}</Text> },
            { key: "cap", title: "Cap", width: 130, render: (row) => <Text>{money(row.cap_balance)}</Text> }
          ]}
        />
      </Panel>
    </Screen>
  );
}
