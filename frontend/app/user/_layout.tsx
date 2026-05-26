import { Redirect } from "expo-router";
import React from "react";

import { AppShell, LoadingState, Screen } from "@/components/ui";
import { useAuth } from "@/context/AuthContext";

const items = [
  { label: "Dashboard", href: "/user", icon: "view-dashboard-outline" as const },
  { label: "Services", href: "/user/services", icon: "flash-outline" as const },
  { label: "Wallet", href: "/user/wallet", icon: "wallet-outline" as const },
  { label: "API Settings", href: "/user/api-settings", icon: "api" as const },
  { label: "Onboarding", href: "/user/kyc", icon: "clipboard-account-outline" as const },
  { label: "Reports", href: "/user/reports", icon: "chart-box-outline" as const }
];

export default function UserLayout() {
  const { user, loading, isAdmin } = useAuth();
  if (loading) {
    return (
      <Screen>
        <LoadingState />
      </Screen>
    );
  }
  if (!user) return <Redirect href="/login" />;
  if (isAdmin) return <Redirect href="/admin" />;
  return <AppShell title="User Panel" items={items} />;
}
