import { Redirect } from "expo-router";
import React from "react";

import { LoadingState, Screen } from "@/components/ui";
import { useAuth } from "@/context/AuthContext";

export default function Index() {
  const { user, loading, isAdmin } = useAuth();

  if (loading) {
    return (
      <Screen>
        <LoadingState />
      </Screen>
    );
  }

  if (!user) return <Redirect href="/login" />;
  return <Redirect href={isAdmin ? "/admin" : "/user"} />;
}
