import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import React, { useState } from "react";
import { Text } from "react-native";

import { api } from "@/api/client";
import { Button, DataTable, ErrorText, Field, Grid, Panel, Screen, SelectBox, StatCard, StatusBadge } from "@/components/ui";
import type { FundRequest, PaymentGatewayOrder } from "@/types";
import { dateTime, money } from "@/utils/format";

export default function UserWallet() {
  const queryClient = useQueryClient();
  const [amount, setAmount] = useState("1000");
  const [method, setMethod] = useState<FundRequest["method"]>("upi");
  const [reference, setReference] = useState("");
  const [note, setNote] = useState("");
  const [gatewayAmount, setGatewayAmount] = useState("500");
  const [gatewayOrder, setGatewayOrder] = useState<PaymentGatewayOrder | null>(null);
  const [error, setError] = useState("");

  const wallet = useQuery({ queryKey: ["wallet-mine"], queryFn: api.walletMine });
  const funds = useQuery({ queryKey: ["fund-requests", "mine"], queryFn: () => api.fundRequests() });
  const ledger = useQuery({ queryKey: ["wallet-ledger"], queryFn: () => api.ledger() });

  const createFund = useMutation({
    mutationFn: () => api.createFundRequest({ amount, method, payment_reference: reference, note }),
    onSuccess: () => {
      setReference("");
      setNote("");
      setError("");
      queryClient.invalidateQueries({ queryKey: ["fund-requests"] });
    },
    onError: (err) => setError(err instanceof Error ? err.message : "Fund request failed.")
  });

  const createGateway = useMutation({
    mutationFn: () => api.createGatewayOrder(gatewayAmount),
    onSuccess: (order) => {
      setGatewayOrder(order);
      setError("");
    },
    onError: (err) => setError(err instanceof Error ? err.message : "Payment order failed.")
  });

  const completeGateway = useMutation({
    mutationFn: () => {
      if (!gatewayOrder) {
        throw new Error("No payment order to complete.");
      }
      return api.completeGatewayOrder(gatewayOrder.id, "success");
    },
    onSuccess: (order) => {
      setGatewayOrder(order);
      setError("");
      queryClient.invalidateQueries({ queryKey: ["wallet-mine"] });
      queryClient.invalidateQueries({ queryKey: ["wallet-ledger"] });
    },
    onError: (err) => setError(err instanceof Error ? err.message : "Payment order failed.")
  });

  return (
    <Screen title="Wallet">
      <Grid>
        <StatCard label="Available" value={money(wallet.data?.available_balance)} icon="wallet-outline" tone="green" />
        <StatCard label="Hold" value={money(wallet.data?.hold_balance)} icon="lock-clock" tone="amber" />
        <StatCard label="Cap Balance" value={money(wallet.data?.cap_balance)} icon="speedometer" tone="cyan" />
      </Grid>

      <Panel title="Fund Request">
        <Grid>
          <Field label="Amount" value={amount} onChangeText={setAmount} keyboardType="numeric" />
          <SelectBox
            label="Method"
            value={method}
            options={[
              { label: "UPI", value: "upi" },
              { label: "Bank", value: "bank" },
              { label: "Cash", value: "cash" },
              { label: "Gateway", value: "gateway" }
            ]}
            onChange={setMethod}
          />
          <Field label="Payment Reference" value={reference} onChangeText={setReference} />
          <Field label="Note" value={note} onChangeText={setNote} />
        </Grid>
        <ErrorText message={error} />
        <Button icon="bank-transfer-in" onPress={() => createFund.mutate()} disabled={!amount}>Submit Fund Request</Button>
      </Panel>

      <Panel title="Payment Gateway">
        <Grid>
          <Field label="Amount" value={gatewayAmount} onChangeText={setGatewayAmount} keyboardType="numeric" />
          <Button icon="credit-card-outline" variant="secondary" onPress={() => createGateway.mutate()} disabled={!gatewayAmount || createGateway.isPending}>Create Payment Link</Button>
        </Grid>
        {gatewayOrder ? (
          <Grid>
            <Text>Gateway Provider: {gatewayOrder.provider_name || "Payment Gateway"}</Text>
            <Text selectable>Payment Link: {gatewayOrder.payment_link || gatewayOrder.reference}</Text>
            <Text>Order Status: {gatewayOrder.status}</Text>
          </Grid>
        ) : null}
        <Text>
          {gatewayOrder?.sandbox_mode
            ? "Sandbox checkout is enabled. Create the order, then confirm payment to credit the wallet while gateway credentials remain dummy."
            : "Live gateway mode is enabled once provider credentials and endpoint configuration are ready."}
        </Text>
        <Button icon="check-decagram-outline" onPress={() => completeGateway.mutate()} disabled={!gatewayOrder || gatewayOrder.status !== "created" || completeGateway.isPending}>Confirm Payment</Button>
      </Panel>

      <Panel title="Fund Requests">
        <DataTable
          data={funds.data}
          keyExtractor={(row) => String(row.id)}
          columns={[
            { key: "amount", title: "Amount", width: 130, render: (row) => <Text>{money(row.amount)}</Text> },
            { key: "method", title: "Method", width: 110, render: (row) => <Text>{row.method}</Text> },
            { key: "ref", title: "Reference", width: 180, render: (row) => <Text>{row.payment_reference || "-"}</Text> },
            { key: "status", title: "Status", width: 130, render: (row) => <StatusBadge status={row.status} /> },
            { key: "date", title: "Date", width: 190, render: (row) => <Text>{dateTime(row.created_at)}</Text> }
          ]}
        />
      </Panel>

      <Panel title="Wallet Ledger">
        <DataTable
          data={ledger.data}
          keyExtractor={(row) => String(row.id)}
          columns={[
            { key: "type", title: "Type", width: 160, render: (row) => <Text>{row.entry_type}</Text> },
            { key: "ref", title: "Reference", width: 180, render: (row) => <Text>{row.transaction_ref}</Text> },
            { key: "opening", title: "Opening", width: 130, render: (row) => <Text>{money(row.opening_balance)}</Text> },
            { key: "amount", title: "Amount", width: 130, render: (row) => <Text>{money(row.amount)}</Text> },
            { key: "closing", title: "Closing", width: 130, render: (row) => <Text>{money(row.closing_balance)}</Text> },
            { key: "remarks", title: "Remarks", width: 260, render: (row) => <Text>{row.remarks}</Text> }
          ]}
        />
      </Panel>
    </Screen>
  );
}
