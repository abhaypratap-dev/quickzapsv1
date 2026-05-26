import { Redirect } from "expo-router";
import React from "react";

import { AppShell, LoadingState, Screen } from "@/components/ui";
import { useAuth } from "@/context/AuthContext";

const items = [
  { label: "Dashboard", href: "/admin", icon: "view-dashboard-outline" as const },
  { label: "Users", href: "/admin/users", icon: "account-group-outline" as const },
  { label: "Onboarding", href: "/admin/kyc", icon: "clipboard-check-outline" as const },
  { label: "Payments", href: "/admin/payments", icon: "bank-transfer" as const },
  { label: "Commissions", href: "/admin/commissions", icon: "percent-outline" as const },
  { label: "Settings", href: "/admin/settings", icon: "cog-outline" as const },
  { label: "APIs", href: "/admin/apis", icon: "api" as const },
  { label: "Reports", href: "/admin/reports", icon: "chart-box-outline" as const }
];

export default function AdminLayout() {
  const { user, loading, isAdmin } = useAuth();
  if (loading) {
    return (
      <Screen>
        <LoadingState />
      </Screen>
    );
  }
  if (!user) return <Redirect href="/login" />;
  if (!isAdmin) return <Redirect href="/user" />;
  return <AppShell title="Admin Panel" items={items} />;
}
