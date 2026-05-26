import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import React, { useState } from "react";
import { Text } from "react-native";

import { api } from "@/api/client";
import { Button, DataTable, Field, Grid, Panel, Screen, SelectBox, StatusBadge } from "@/components/ui";
import { useTheme } from "@/context/ThemeContext";
import type { ID, User } from "@/types";
import { money } from "@/utils/format";

export default function AdminUsers() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const { colors } = useTheme();
  const [filter, setFilter] = useState<User["status"] | "all">("active");
  const [search, setSearch] = useState("");

  const users = useQuery({ queryKey: ["users", filter, search], queryFn: () => api.users({ status: filter === "all" ? "" : filter, search }) });
  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: ID; status: User["status"] }) => api.setUserStatus(id, status),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] })
  });

  return (
    <Screen title="Manage Users">
      <Panel title="User Creation Is Onboarding Only" action={<Button icon="clipboard-check-outline" onPress={() => router.push("/admin/kyc")}>Review Queue</Button>}>
        <Text style={{ color: colors.muted, fontWeight: "700" }}>
          Direct admin user creation has been disabled in the UI. New SDBR, DBR and Retailer accounts are created only after the onboarding verification and approval flow.
        </Text>
      </Panel>

      <Panel title="Users">
        <Grid>
          <SelectBox
            label="Status"
            value={filter}
            options={[
              { label: "Active", value: "active" },
              { label: "Inactive", value: "inactive" },
              { label: "Signup", value: "signup" },
              { label: "Deleted", value: "deleted" },
              { label: "All", value: "all" }
            ]}
            onChange={setFilter}
          />
          <Field label="Common Search" value={search} onChangeText={setSearch} />
        </Grid>
        <DataTable
          data={users.data}
          keyExtractor={(row) => String(row.id)}
          columns={[
            { key: "mobile", title: "User ID", width: 130, render: (row) => <Text>{row.mobile}</Text> },
            { key: "name", title: "Name", width: 180, render: (row) => <Text>{`${row.first_name} ${row.last_name}`.trim()}</Text> },
            { key: "role", title: "Role", width: 160, render: (row) => <Text>{row.role_name}</Text> },
            { key: "parent", title: "Parent", width: 150, render: (row) => <Text>{row.parent_mobile || "-"}</Text> },
            { key: "wallet", title: "Wallet", width: 140, render: (row) => <Text>{money(row.wallet?.available_balance)}</Text> },
            { key: "kyc", title: "KYC", width: 150, render: (row) => <StatusBadge status={row.kyc_status} /> },
            { key: "status", title: "Status", width: 130, render: (row) => <StatusBadge status={row.status} /> },
            {
              key: "actions",
              title: "Actions",
              width: 310,
              render: (row) => (
                <Grid>
                  {row.status !== "active" && <Button icon="check" onPress={() => setStatus.mutate({ id: row.id, status: "active" })}>Activate</Button>}
                  {row.status === "active" && <Button icon="pause" variant="ghost" onPress={() => setStatus.mutate({ id: row.id, status: "inactive" })}>Block</Button>}
                  {row.status !== "deleted" && <Button icon="delete-outline" variant="danger" onPress={() => setStatus.mutate({ id: row.id, status: "deleted" })}>Delete</Button>}
                </Grid>
              )
            }
          ]}
        />
      </Panel>
    </Screen>
  );
}
