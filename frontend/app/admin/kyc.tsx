import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import React, { useState } from "react";
import { Text } from "react-native";

import { api } from "@/api/client";
import { Button, DataTable, Field, Grid, Panel, Screen, SelectBox, StatusBadge } from "@/components/ui";
import type { ID, OnboardingApplication, OnboardingStatus } from "@/types";
import { dateTime } from "@/utils/format";

export default function AdminKyc() {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<OnboardingStatus | "all">("pending_admin");
  const [note, setNote] = useState("");
  const applications = useQuery({
    queryKey: ["onboarding-applications", status],
    queryFn: () => api.onboardingApplications({ status: status === "all" ? "" : status })
  });
  const review = useMutation({
    mutationFn: ({ id, action }: { id: ID; action: "approve" | "reject" }) => api.reviewOnboarding(id, { action, note }),
    onSuccess: () => {
      setNote("");
      queryClient.invalidateQueries({ queryKey: ["onboarding-applications"] });
      queryClient.invalidateQueries({ queryKey: ["users"] });
    }
  });

  return (
    <Screen title="Onboarding Review">
      <Panel title="Approval Queue">
        <Grid>
          <SelectBox
            label="Status"
            value={status}
            options={[
              { label: "Pending Admin", value: "pending_admin" },
              { label: "Pending Parent", value: "pending_parent" },
              { label: "Created", value: "created" },
              { label: "Rejected", value: "rejected" },
              { label: "All", value: "all" }
            ]}
            onChange={setStatus}
          />
          <Field label="Review Note" value={note} onChangeText={setNote} />
        </Grid>
        <DataTable
          data={applications.data}
          keyExtractor={(row) => String(row.id)}
          columns={[
            { key: "date", title: "Submitted", width: 170, render: (row) => <Text>{dateTime(row.created_at)}</Text> },
            { key: "name", title: "Applicant", width: 180, render: (row) => <Text>{row.full_name}</Text> },
            { key: "mobile", title: "Mobile", width: 135, render: (row) => <Text>{row.mobile}</Text> },
            { key: "role", title: "Role", width: 120, render: (row) => <Text>{row.requested_role}</Text> },
            { key: "parent", title: "Parent", width: 190, render: (row) => <Text>{row.parent_mobile || (row.direct_to_admin ? "Admin direct" : "-")}</Text> },
            { key: "pan", title: "PAN", width: 140, render: (row) => <StatusBadge status={String(row.pan_verification?.status || "-")} /> },
            { key: "aadhaar", title: "Aadhaar", width: 140, render: (row) => <StatusBadge status={String(row.aadhaar_verification?.status || row.aadhaar_verification?.digilocker_status || "-")} /> },
            { key: "rpd", title: "RPD", width: 120, render: (row) => <StatusBadge status={row.rpd_status || "-"} /> },
            { key: "status", title: "Status", width: 160, render: (row) => <StatusBadge status={row.status} /> },
            {
              key: "actions",
              title: "Actions",
              width: 240,
              render: (row: OnboardingApplication) => (
                <Grid>
                  {row.status === "pending_admin" && <Button icon="check-decagram-outline" onPress={() => review.mutate({ id: row.id, action: "approve" })}>Approve</Button>}
                  {["pending_admin", "pending_parent"].includes(row.status) && <Button icon="close-octagon-outline" variant="danger" onPress={() => review.mutate({ id: row.id, action: "reject" })}>Reject</Button>}
                </Grid>
              )
            }
          ]}
        />
      </Panel>
    </Screen>
  );
}
