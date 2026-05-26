import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import React, { useState } from "react";
import { Text } from "react-native";

import { api } from "@/api/client";
import { Button, DataTable, ErrorText, Field, Grid, Panel, Screen, SelectBox, StatusBadge } from "@/components/ui";
import type { ID } from "@/types";
import { dateTime, money } from "@/utils/format";

export default function AdminPayments() {
  const queryClient = useQueryClient();
  const [adjustUser, setAdjustUser] = useState<ID | null>(null);
  const [amount, setAmount] = useState("");
  const [direction, setDirection] = useState<"credit" | "debit">("credit");
  const [remarks, setRemarks] = useState("");
  const [error, setError] = useState("");

  const users = useQuery({ queryKey: ["users", "active"], queryFn: () => api.users({ status: "active" }) });
  const funds = useQuery({ queryKey: ["fund-requests"], queryFn: () => api.fundRequests() });
  const wallets = useQuery({ queryKey: ["wallets"], queryFn: () => api.wallets() });

  const userOptions = [{ label: "Select", value: null as ID | null }, ...(users.data || []).map((user) => ({ label: `${user.mobile} ${user.role_name || ""}`, value: user.id }))];

  const adjust = useMutation({
    mutationFn: () => api.adjustWallet({ user: adjustUser, amount, direction, remarks }),
    onSuccess: () => {
      setAmount("");
      setRemarks("");
      setError("");
      queryClient.invalidateQueries({ queryKey: ["wallets"] });
      queryClient.invalidateQueries({ queryKey: ["fund-requests"] });
    },
    onError: (err) => setError(err instanceof Error ? err.message : "Adjustment failed.")
  });

  const review = useMutation({
    mutationFn: ({ id, status }: { id: ID; status: "approved" | "rejected" }) => api.reviewFundRequest(id, { status, review_note: remarks }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["fund-requests"] });
      queryClient.invalidateQueries({ queryKey: ["wallets"] });
    }
  });

  return (
    <Screen title="Payments">
      <Panel title="Add Balance">
        <Grid>
          <SelectBox label="User" value={adjustUser} options={userOptions} onChange={setAdjustUser} />
          <SelectBox
            label="Direction"
            value={direction}
            options={[
              { label: "Credit", value: "credit" },
              { label: "Debit", value: "debit" }
            ]}
            onChange={setDirection}
          />
          <Field label="Amount" value={amount} onChangeText={setAmount} keyboardType="numeric" />
          <Field label="Remarks" value={remarks} onChangeText={setRemarks} />
        </Grid>
        <ErrorText message={error} />
        <Button icon="wallet-plus-outline" onPress={() => adjust.mutate()} disabled={!adjustUser || !amount || !remarks}>
          Save Adjustment
        </Button>
      </Panel>

      <Panel title="Fund Requests">
        <DataTable
          data={funds.data}
          keyExtractor={(row) => String(row.id)}
          columns={[
            { key: "user", title: "User", width: 160, render: (row) => <Text>{row.user_mobile}</Text> },
            { key: "amount", title: "Amount", width: 140, render: (row) => <Text>{money(row.amount)}</Text> },
            { key: "method", title: "Method", width: 110, render: (row) => <Text>{row.method}</Text> },
            { key: "ref", title: "Reference", width: 180, render: (row) => <Text>{row.payment_reference || "-"}</Text> },
            { key: "status", title: "Status", width: 130, render: (row) => <StatusBadge status={row.status} /> },
            { key: "date", title: "Date", width: 190, render: (row) => <Text>{dateTime(row.created_at)}</Text> },
            {
              key: "actions",
              title: "Actions",
              width: 230,
              render: (row) => (
                <Grid>
                  {row.status === "pending" && <Button icon="check" onPress={() => review.mutate({ id: row.id, status: "approved" })}>Approve</Button>}
                  {row.status === "pending" && <Button icon="close" variant="danger" onPress={() => review.mutate({ id: row.id, status: "rejected" })}>Reject</Button>}
                </Grid>
              )
            }
          ]}
        />
      </Panel>

      <Panel title="Wallet Summary">
        <DataTable
          data={wallets.data}
          keyExtractor={(row) => String(row.id)}
          columns={[
            { key: "user", title: "User", width: 160, render: (row) => <Text>{row.user_mobile}</Text> },
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
