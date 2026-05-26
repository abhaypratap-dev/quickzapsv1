import * as SecureStore from "expo-secure-store";
import React, { createContext, PropsWithChildren, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { Platform } from "react-native";

import { api, setApiTokens } from "@/api/client";
import type { User } from "@/types";

type StoredSession = {
  access: string;
  refresh: string;
  user: User;
};

type AuthContextValue = {
  user: User | null;
  access: string | null;
  refresh: string | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  reloadUser: () => Promise<void>;
  isAdmin: boolean;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);
const storageKey = "quickzaps.session";

async function readSession(): Promise<StoredSession | null> {
  try {
    const raw =
      Platform.OS === "web"
        ? globalThis.localStorage?.getItem(storageKey)
        : await SecureStore.getItemAsync(storageKey);
    return raw ? (JSON.parse(raw) as StoredSession) : null;
  } catch {
    return null;
  }
}

async function writeSession(session: StoredSession | null) {
  if (session) {
    const raw = JSON.stringify(session);
    if (Platform.OS === "web") {
      globalThis.localStorage?.setItem(storageKey, raw);
    } else {
      await SecureStore.setItemAsync(storageKey, raw);
    }
  } else if (Platform.OS === "web") {
    globalThis.localStorage?.removeItem(storageKey);
  } else {
    await SecureStore.deleteItemAsync(storageKey);
  }
}

export function AuthProvider({ children }: PropsWithChildren) {
  const [user, setUser] = useState<User | null>(null);
  const [access, setAccess] = useState<string | null>(null);
  const [refresh, setRefresh] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const persist = useCallback(async (session: StoredSession | null) => {
    setUser(session?.user ?? null);
    setAccess(session?.access ?? null);
    setRefresh(session?.refresh ?? null);
    setApiTokens({ access: session?.access ?? null, refresh: session?.refresh ?? null });
    await writeSession(session);
  }, []);

  useEffect(() => {
    let mounted = true;
    readSession()
      .then(async (session) => {
        if (!mounted) return;
        if (session) {
          setApiTokens({ access: session.access, refresh: session.refresh });
          setUser(session.user);
          setAccess(session.access);
          setRefresh(session.refresh);
          try {
            const currentUser = await api.me();
            await persist({ ...session, user: currentUser });
          } catch {
            await persist(null);
          }
        }
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [persist]);

  const login = useCallback(
    async (username: string, password: string) => {
      const response = await api.login(username, password);
      await persist(response);
    },
    [persist]
  );

  const logout = useCallback(async () => {
    await persist(null);
  }, [persist]);

  const reloadUser = useCallback(async () => {
    const currentUser = await api.me();
    if (access && refresh) {
      await persist({ access, refresh, user: currentUser });
    } else {
      setUser(currentUser);
    }
  }, [access, refresh, persist]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      access,
      refresh,
      loading,
      login,
      logout,
      reloadUser,
      isAdmin: user?.role_code === "SUPER_ADMIN" || user?.role_code === "ADMIN"
    }),
    [access, loading, login, logout, refresh, reloadUser, user]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return context;
}
