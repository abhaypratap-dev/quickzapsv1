import { MaterialCommunityIcons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import React, { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { Button, ErrorText, Field, ThemeToggle } from "@/components/ui";
import { useAuth } from "@/context/AuthContext";
import { useTheme } from "@/context/ThemeContext";
import { shadowsDark, shadows as shadowsLight, spacing } from "@/theme";

export default function LoginScreen() {
  const router = useRouter();
  const { login } = useAuth();
  const { colors, isDark } = useTheme();
  const [username, setUsername] = useState("9000000000");
  const [password, setPassword] = useState("Admin@12345");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const shadow = isDark ? shadowsDark.panel : shadowsLight.panel;

  async function submit() {
    setBusy(true);
    setError("");
    try {
      await login(username, password);
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={[s.page, { backgroundColor: colors.page }]}>
      {/* Theme toggle in top-right corner */}
      <View style={s.topRight}>
        <ThemeToggle />
      </View>

      {/* Brand panel */}
      <View style={[s.brandPanel, { backgroundColor: colors.panel, borderColor: colors.line, ...shadow }]}>
        <View style={[s.logo, { backgroundColor: colors.brand }]}>
          <Text style={s.logoText}>QZ</Text>
        </View>
        <Text style={[s.title, { color: colors.ink }]}>QuickZaps</Text>
        <Text style={[s.subtitle, { color: colors.brandStrong }]}>Serve More · Earn More</Text>
        <View style={s.divider} />
        <View style={s.metrics}>
          {[
            { icon: "shield-check-outline" as const,          color: colors.green,  text: "JWT-secured REST API" },
            { icon: "wallet-outline" as const,                color: colors.brand,  text: "Ledger-backed wallet" },
            { icon: "swap-horizontal-circle-outline" as const, color: colors.teal,  text: "Sandbox & live provider routing" },
            { icon: "account-group-outline" as const,          color: colors.violet, text: "Role-based access control" },
          ].map(({ icon, color, text }) => (
            <View key={text} style={s.metric}>
              <MaterialCommunityIcons name={icon} size={18} color={color} />
              <Text style={[s.metricText, { color: colors.ink }]}>{text}</Text>
            </View>
          ))}
        </View>
      </View>

      {/* Login form */}
      <View style={[s.formPanel, { backgroundColor: colors.panel, borderColor: colors.line, ...shadow }]}>
        <View>
          <Text style={[s.formTitle, { color: colors.ink }]}>Welcome back</Text>
          <Text style={[s.formSub, { color: colors.muted }]}>Sign in to your account</Text>
        </View>
        <Field label="Mobile / User ID" value={username} onChangeText={setUsername} keyboardType="phone-pad" placeholder="9XXXXXXXXX" />
        <Field label="Password" value={password} onChangeText={setPassword} secureTextEntry placeholder="••••••••" />
        <ErrorText message={error} />
        <Button icon="login" onPress={submit} disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </Button>
        <View style={s.divider} />
        <Text style={[s.quickLabel, { color: colors.faint }]}>Quick fill</Text>
        <View style={s.quickLogins}>
          {[
            { label: "Admin",    mobile: "9000000000", pass: "Admin@12345" },
            { label: "Retailer", mobile: "9000000003", pass: "Demo@12345"  },
            { label: "API User", mobile: "9000000004", pass: "Demo@12345"  },
          ].map(({ label, mobile, pass }) => (
            <Pressable
              key={mobile}
              style={({ pressed }) => [s.quickLogin, { backgroundColor: colors.brandMuted }, pressed && { opacity: 0.7 }]}
              onPress={() => { setUsername(mobile); setPassword(pass); }}
            >
              <Text style={[s.quickLoginText, { color: colors.brand }]}>{label}</Text>
            </Pressable>
          ))}
        </View>
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  page:          { alignItems: "center", flex: 1, flexDirection: "row", flexWrap: "wrap", gap: spacing.xl, justifyContent: "center", padding: spacing.xl },
  topRight:      { position: "absolute", top: spacing.lg, right: spacing.lg },
  brandPanel:    { borderRadius: 12, borderWidth: 1, gap: spacing.md, maxWidth: 440, minWidth: 300, padding: spacing.xl },
  logo:          { alignItems: "center", borderRadius: 12, height: 60, justifyContent: "center", width: 60 },
  logoText:      { color: "#FFFFFF", fontSize: 22, fontWeight: "900" },
  title:         { fontSize: 36, fontWeight: "900" },
  subtitle:      { fontSize: 15, fontWeight: "700", letterSpacing: 1, textTransform: "uppercase" },
  divider:       { height: 1, backgroundColor: "#D7DEE8", borderRadius: 999, marginVertical: spacing.xs },
  metrics:       { gap: spacing.sm },
  metric:        { alignItems: "center", flexDirection: "row", gap: spacing.sm },
  metricText:    { fontSize: 14, fontWeight: "600" },
  formPanel:     { borderRadius: 12, borderWidth: 1, gap: spacing.md, maxWidth: 400, minWidth: 300, padding: spacing.xl, width: 400 },
  formTitle:     { fontSize: 28, fontWeight: "900" },
  formSub:       { fontSize: 14, fontWeight: "600", marginTop: 2 },
  quickLabel:    { fontSize: 11, fontWeight: "800", letterSpacing: 0.5, textTransform: "uppercase" },
  quickLogins:   { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  quickLogin:    { borderRadius: 8, paddingHorizontal: spacing.md, paddingVertical: spacing.sm },
  quickLoginText:{ fontSize: 13, fontWeight: "800" },
});
