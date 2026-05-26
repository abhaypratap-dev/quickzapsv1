import { MaterialCommunityIcons } from "@expo/vector-icons";
import { Stack, usePathname, useRouter } from "expo-router";
import React, { PropsWithChildren, ReactNode, useMemo } from "react";
import {
  ActivityIndicator,
  Platform,
  Pressable,
  ScrollView,
  StyleProp,
  StyleSheet,
  Text,
  TextInput,
  useWindowDimensions,
  View,
  ViewStyle
} from "react-native";

import { useAuth } from "@/context/AuthContext";
import { useTheme } from "@/context/ThemeContext";
import { Colors, ColorMode, shadowsDark, shadows as shadowsLight, spacing, THEMES, ThemeName } from "@/theme";
import { statusTone } from "@/utils/format";

type IconName = keyof typeof MaterialCommunityIcons.glyphMap;

// Web-only native elements (typed safely for TypeScript + RN)
const WebSelect = "select" as unknown as React.ComponentType<{
  value: string;
  onChange: (e: { target: { value: string } }) => void;
  style: object;
  children: ReactNode;
}>;
const WebOption = "option" as unknown as React.ComponentType<{
  value: string;
  children: ReactNode;
}>;

export function Screen({ children, title, action }: PropsWithChildren<{ title?: string; action?: ReactNode }>) {
  const { colors } = useTheme();
  return (
    <ScrollView style={{ flex: 1, backgroundColor: colors.page }} contentContainerStyle={base.pageInner}>
      {(title || action) && (
        <View style={base.screenHeader}>
          <Text style={[base.screenTitle, { color: colors.ink }]}>{title}</Text>
          {action}
        </View>
      )}
      {children}
    </ScrollView>
  );
}

export function Panel({ children, title, action, style }: PropsWithChildren<{ title?: string; action?: ReactNode; style?: StyleProp<ViewStyle> }>) {
  const { colors, isDark } = useTheme();
  const shadow = isDark ? shadowsDark.panel : shadowsLight.panel;
  return (
    <View style={[base.panel, { backgroundColor: colors.panel, borderColor: colors.line, ...shadow }, style]}>
      {(title || action) && (
        <View style={base.panelHeader}>
          {title ? <Text style={[base.panelTitle, { color: colors.ink }]}>{title}</Text> : <View />}
          {action}
        </View>
      )}
      {children}
    </View>
  );
}

export function Row({ children, style }: PropsWithChildren<{ style?: StyleProp<ViewStyle> }>) {
  return <View style={[base.row, style]}>{children}</View>;
}

export function Grid({ children }: PropsWithChildren) {
  return <View style={base.grid}>{children}</View>;
}

export function Button({
  children,
  icon,
  onPress,
  variant = "primary",
  disabled
}: PropsWithChildren<{ icon?: IconName; onPress?: () => void; variant?: "primary" | "secondary" | "danger" | "ghost"; disabled?: boolean }>) {
  const { colors } = useTheme();
  const bg =
    variant === "primary"   ? colors.brand :
    variant === "secondary" ? colors.teal  :
    variant === "danger"    ? colors.red   :
    colors.brandMuted;
  const fg = variant === "ghost" ? colors.brand : colors.white;
  return (
    <Pressable
      accessibilityRole="button"
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [
        base.button,
        { backgroundColor: bg },
        disabled && base.btnDisabled,
        pressed && !disabled && base.pressed
      ]}
    >
      {icon && <MaterialCommunityIcons name={icon} size={18} color={fg} />}
      <Text style={[base.btnText, { color: fg }]}>{children}</Text>
    </Pressable>
  );
}

export function IconButton({
  icon,
  label,
  onPress,
  variant = "ghost",
  disabled
}: {
  icon: IconName;
  label: string;
  onPress?: () => void;
  variant?: "primary" | "ghost" | "danger";
  disabled?: boolean;
}) {
  const { colors } = useTheme();
  const bg =
    variant === "primary" ? colors.brand :
    variant === "danger"  ? colors.red   :
    colors.brandMuted;
  const fg = variant === "ghost" ? colors.brand : colors.white;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [
        base.iconBtn,
        { backgroundColor: bg },
        disabled && base.btnDisabled,
        pressed && !disabled && base.pressed
      ]}
    >
      <MaterialCommunityIcons name={icon} size={20} color={fg} />
    </Pressable>
  );
}

export function Field({
  label,
  value,
  onChangeText,
  placeholder,
  secureTextEntry,
  keyboardType = "default",
  multiline,
  style
}: {
  label: string;
  value: string;
  onChangeText: (value: string) => void;
  placeholder?: string;
  secureTextEntry?: boolean;
  keyboardType?: "default" | "numeric" | "email-address" | "phone-pad";
  multiline?: boolean;
  style?: StyleProp<ViewStyle>;
}) {
  const { colors } = useTheme();
  return (
    <View style={[base.field, style]}>
      <Text style={[base.label, { color: colors.muted }]}>{label}</Text>
      <TextInput
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={colors.faint}
        secureTextEntry={secureTextEntry}
        keyboardType={keyboardType}
        multiline={multiline}
        style={[
          base.input,
          { backgroundColor: colors.inputBg, borderColor: colors.inputBorder, color: colors.ink },
          multiline && base.textarea
        ]}
      />
    </View>
  );
}

// SelectBox: native <select> on web, chip strip on native
export function SelectBox<T extends string | number | null>({
  label,
  value,
  options,
  onChange
}: {
  label: string;
  value: T;
  options: Array<{ label: string; value: T }>;
  onChange: (value: T) => void;
}) {
  const { colors } = useTheme();
  const strValue = value === null ? "" : String(value);

  const handleWebChange = (e: { target: { value: string } }) => {
    const v = e.target.value;
    const found = options.find((o) => (o.value === null ? "" : String(o.value)) === v);
    if (found !== undefined) onChange(found.value);
  };

  const chevron = colors.muted.replace("#", "%23");
  const webSelectStyle = {
    appearance: "none",
    WebkitAppearance: "none",
    backgroundColor: colors.inputBg,
    border: `1.5px solid ${colors.inputBorder}`,
    borderRadius: 8,
    color: colors.ink,
    fontSize: 14,
    fontWeight: "600",
    height: 44,
    paddingLeft: 12,
    paddingRight: 36,
    cursor: "pointer",
    outline: "none",
    width: "100%",
    transition: "border-color 0.15s",
    backgroundImage: `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='20' height='20' viewBox='0 0 24 24'><path fill='${chevron}' d='M7 10l5 5 5-5z'/></svg>")`,
    backgroundRepeat: "no-repeat",
    backgroundPosition: "right 10px center",
  };

  return (
    <View style={base.field}>
      <Text style={[base.label, { color: colors.muted }]}>{label}</Text>
      {Platform.OS === "web" ? (
        <WebSelect value={strValue} onChange={handleWebChange} style={webSelectStyle as object}>
          {options.map((o) => (
            <WebOption key={String(o.value)} value={o.value === null ? "" : String(o.value)}>
              {o.label}
            </WebOption>
          ))}
        </WebSelect>
      ) : (
        <View style={base.chipWrap}>
          {options.map((o) => {
            const active = o.value === value;
            return (
              <Pressable
                key={String(o.value)}
                onPress={() => onChange(o.value)}
                style={[base.chip, { borderColor: active ? colors.brand : colors.line }, active && { backgroundColor: colors.brand }]}
              >
                <Text style={[base.chipText, { color: active ? colors.white : colors.ink }]}>{o.label}</Text>
              </Pressable>
            );
          })}
        </View>
      )}
    </View>
  );
}

export function Toggle({ label, value, onChange }: { label: string; value: boolean; onChange: (value: boolean) => void }) {
  const { colors } = useTheme();
  return (
    <Pressable onPress={() => onChange(!value)} style={base.toggleRow}>
      <View style={[base.toggleTrack, { backgroundColor: value ? colors.green : colors.line }]}>
        <View style={[base.toggleDot, value && base.toggleDotOn]} />
      </View>
      <Text style={[base.toggleLabel, { color: colors.ink }]}>{label}</Text>
    </Pressable>
  );
}

const badgeTones: Record<string, { bg: string; fg: string }> = {
  neutral: { bg: "#EDF1F5", fg: "#647084" },
  green:   { bg: "#E8F5EE", fg: "#1F8A4C" },
  amber:   { bg: "#FFF2DF", fg: "#B26B12" },
  red:     { bg: "#FBECEA", fg: "#BE3A34" },
  violet:  { bg: "#F0ECF8", fg: "#6B4CA3" },
};

export function StatusBadge({ status }: { status?: string }) {
  const tone = statusTone(status);
  const { bg, fg } = badgeTones[tone] ?? badgeTones.neutral;
  return (
    <View style={[base.badge, { backgroundColor: bg }]}>
      <Text style={[base.badgeText, { color: fg }]}>{status ?? "unknown"}</Text>
    </View>
  );
}

const statTones: Record<string, { bg: string; fg: string }> = {
  brand:  { bg: "#E6F0F8", fg: "#265C8F" },
  green:  { bg: "#E8F5EE", fg: "#1F8A4C" },
  red:    { bg: "#FBECEA", fg: "#BE3A34" },
  amber:  { bg: "#FFF2DF", fg: "#B26B12" },
  teal:   { bg: "#E7F4F2", fg: "#117A72" },
  violet: { bg: "#F0ECF8", fg: "#6B4CA3" },
  cyan:   { bg: "#E7F4FA", fg: "#327E9D" },
};

export function StatCard({
  label,
  value,
  icon,
  tone = "brand"
}: {
  label: string;
  value: string | number;
  icon: IconName;
  tone?: "brand" | "green" | "red" | "amber" | "teal" | "violet" | "cyan";
}) {
  const { colors, isDark } = useTheme();
  const shadow = isDark ? shadowsDark.panel : shadowsLight.panel;
  const { bg, fg } = statTones[tone] ?? statTones.brand;
  return (
    <View style={[base.statCard, { backgroundColor: colors.panel, borderColor: colors.line, ...shadow }]}>
      <View style={[base.statIcon, { backgroundColor: bg }]}>
        <MaterialCommunityIcons name={icon} size={21} color={fg} />
      </View>
      <View style={base.statText}>
        <Text style={[base.statLabel, { color: colors.muted }]}>{label}</Text>
        <Text style={[base.statValue, { color: colors.ink }]}>{value}</Text>
      </View>
    </View>
  );
}

export function EmptyState({ title }: { title: string }) {
  const { colors } = useTheme();
  return (
    <View style={[base.empty, { borderColor: colors.line }]}>
      <MaterialCommunityIcons name="database-search-outline" size={24} color={colors.faint} />
      <Text style={[base.emptyText, { color: colors.muted }]}>{title}</Text>
    </View>
  );
}

export function LoadingState() {
  const { colors } = useTheme();
  return (
    <View style={base.loading}>
      <ActivityIndicator color={colors.brand} size="large" />
    </View>
  );
}

export function ErrorText({ message }: { message?: string }) {
  const { colors } = useTheme();
  if (!message) return null;
  return (
    <View style={[base.errorBox, { backgroundColor: `${colors.red}18`, borderColor: `${colors.red}44` }]}>
      <MaterialCommunityIcons name="alert-circle-outline" size={16} color={colors.red} />
      <Text style={[base.errorText, { color: colors.red }]}>{message}</Text>
    </View>
  );
}

export function DataTable<T>({
  columns,
  data,
  keyExtractor,
  empty = "No records found"
}: {
  columns: Array<{ key: string; title: string; render: (row: T) => ReactNode; width?: number }>;
  data?: T[];
  keyExtractor: (row: T, index: number) => string;
  empty?: string;
}) {
  const { colors } = useTheme();
  if (!data) return <LoadingState />;
  if (!data.length) return <EmptyState title={empty} />;
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false}>
      <View style={base.table}>
        <View style={[base.tableHead, { backgroundColor: colors.panelAlt }]}>
          {columns.map((col) => (
            <Text key={col.key} style={[base.tableHeadCell, { color: colors.muted, width: col.width ?? 150 }]}>
              {col.title}
            </Text>
          ))}
        </View>
        {data.map((row, index) => (
          <View
            key={keyExtractor(row, index)}
            style={[base.tableRow, { borderBottomColor: colors.line }, index % 2 === 1 && { backgroundColor: colors.panelAlt }]}
          >
            {columns.map((col) => (
              <View key={col.key} style={[base.tableCell, { width: col.width ?? 150 }]}>
                {col.render(row)}
              </View>
            ))}
          </View>
        ))}
      </View>
    </ScrollView>
  );
}

// ─── ThemeToggle – cycles light → dark → system ──────────────────────────────
export function ThemeToggle() {
  const { colorMode, setColorMode, colors } = useTheme();
  const next: Record<ColorMode, ColorMode> = { light: "dark", dark: "system", system: "light" };
  const icon: Record<ColorMode, IconName> = { light: "weather-sunny", dark: "weather-night", system: "theme-light-dark" };
  const tip:  Record<ColorMode, string>   = { light: "Light mode",    dark: "Dark mode",     system: "Auto (system)"  };
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={tip[colorMode]}
      onPress={() => setColorMode(next[colorMode])}
      style={({ pressed }) => [base.iconBtn, { backgroundColor: colors.brandMuted }, pressed && base.pressed]}
    >
      <MaterialCommunityIcons name={icon[colorMode]} size={20} color={colors.brand} />
    </Pressable>
  );
}

// ─── ThemeSchemePicker – 4 colour scheme cards ────────────────────────────────
export function ThemeSchemePicker() {
  const { themeName, setThemeName, colors } = useTheme();
  return (
    <View style={{ flexDirection: "row", gap: spacing.sm, flexWrap: "wrap" }}>
      {(Object.entries(THEMES) as Array<[ThemeName, (typeof THEMES)[ThemeName]]>).map(([name, def]) => {
        const active = themeName === name;
        return (
          <Pressable
            key={name}
            onPress={() => setThemeName(name)}
            accessibilityRole="radio"
            accessibilityLabel={def.label}
            style={({ pressed }) => [
              base.schemeCard,
              { borderColor: active ? def.accent : colors.line, backgroundColor: active ? `${def.accent}18` : colors.panelAlt },
              pressed && base.pressed
            ]}
          >
            <View style={[base.schemeDot, { backgroundColor: def.accent }]} />
            <Text style={[base.schemeLabel, { color: active ? def.accent : colors.muted }]}>{def.label}</Text>
            {active && <MaterialCommunityIcons name="check-circle" size={14} color={def.accent} />}
          </Pressable>
        );
      })}
    </View>
  );
}

type NavItem = { label: string; href: string; icon: IconName };

export function AppShell({ items, title }: { items: NavItem[]; title: string }) {
  const { user, logout } = useAuth();
  const { colors, isDark } = useTheme();
  const pathname = usePathname();
  const router = useRouter();
  const { width } = useWindowDimensions();
  const compact = width < 800;

  const sh = useAppShellStyles(colors, isDark, compact);

  return (
    <View style={sh.shell}>
      {/* Sidebar */}
      <View style={sh.sidebar}>
        <View style={sh.brandBlock}>
          <View style={[sh.brandMark, { backgroundColor: colors.brand }]}>
            <Text style={sh.brandMarkText}>QZ</Text>
          </View>
          {!compact && (
            <View>
              <Text style={[sh.brandTitle, { color: colors.ink }]}>QuickZaps</Text>
              <Text style={[sh.brandSub, { color: colors.muted }]}>{title}</Text>
            </View>
          )}
        </View>
        <ScrollView contentContainerStyle={{ gap: 4 }}>
          {items.map((item) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Pressable
                key={item.href}
                onPress={() => router.push(item.href as any)}
                style={({ pressed }) => [
                  sh.navItem,
                  active && { backgroundColor: colors.navActive },
                  pressed && !active && base.pressed
                ]}
              >
                <MaterialCommunityIcons name={item.icon} size={20} color={active ? colors.brandStrong : colors.muted} />
                {!compact && (
                  <Text style={[sh.navText, { color: active ? colors.brandStrong : colors.muted, fontWeight: active ? "800" : "600" }]}>
                    {item.label}
                  </Text>
                )}
              </Pressable>
            );
          })}
        </ScrollView>
      </View>

      {/* Main content */}
      <View style={{ flex: 1, minWidth: 0 }}>
        <View style={sh.topbar}>
          <View>
            <Text style={[sh.topbarTitle, { color: colors.ink }]}>{title}</Text>
            <Text style={[sh.topbarSub, { color: colors.muted }]}>
              {user?.mobile} · {user?.role_name}
            </Text>
          </View>
          <View style={sh.topActions}>
            <ThemeToggle />
            <IconButton icon="account-circle-outline" label="Profile" onPress={() => router.push("/profile")} />
            <IconButton icon="logout" label="Logout" variant="danger" onPress={logout} />
          </View>
        </View>
        <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: "transparent" } }} />
      </View>
    </View>
  );
}

function useAppShellStyles(colors: Colors, isDark: boolean, compact: boolean) {
  return useMemo(
    () =>
      StyleSheet.create({
        shell:        { backgroundColor: colors.page, flex: 1, flexDirection: "row" },
        sidebar:      { backgroundColor: colors.panel, borderRightColor: colors.line, borderRightWidth: 1, padding: spacing.md, width: compact ? 68 : 248 },
        brandBlock:   { alignItems: "center", flexDirection: "row", gap: spacing.sm, marginBottom: spacing.md },
        brandMark:    { alignItems: "center", borderRadius: 10, height: 42, justifyContent: "center", width: 42 },
        brandMarkText:{ color: "#FFFFFF", fontSize: 15, fontWeight: "900" },
        brandTitle:   { fontSize: 17, fontWeight: "900" },
        brandSub:     { fontSize: 11, fontWeight: "700", textTransform: "uppercase", letterSpacing: 0.5 },
        navItem:      { alignItems: "center", borderRadius: 8, flexDirection: "row", gap: spacing.sm, minHeight: 44, paddingHorizontal: spacing.sm },
        navText:      { fontSize: 14 },
        topbar:       { alignItems: "center", backgroundColor: colors.panel, borderBottomColor: colors.line, borderBottomWidth: 1, flexDirection: "row", justifyContent: "space-between", minHeight: 68, paddingHorizontal: spacing.lg },
        topbarTitle:  { fontSize: 18, fontWeight: "900" },
        topbarSub:    { fontSize: 12, fontWeight: "600" },
        topActions:   { alignItems: "center", flexDirection: "row", gap: spacing.sm },
      }),
    [colors, isDark, compact]
  );
}

// ─── Static base styles (layout & spacing only – no theme colours) ───────────────────
const base = StyleSheet.create({
  // Page / Screen
  pageInner:    { padding: spacing.lg, gap: spacing.lg },
  screenHeader: { alignItems: "center", flexDirection: "row", justifyContent: "space-between", gap: spacing.md },
  screenTitle:  { fontSize: 24, fontWeight: "800" },
  // Panel
  panel:        { borderRadius: 10, borderWidth: 1, padding: spacing.lg, gap: spacing.md },
  panelHeader:  { alignItems: "center", flexDirection: "row", justifyContent: "space-between", gap: spacing.sm },
  panelTitle:   { fontSize: 17, fontWeight: "800" },
  // Layout helpers
  row:          { flexDirection: "row", flexWrap: "wrap", gap: spacing.md },
  grid:         { flexDirection: "row", flexWrap: "wrap", gap: spacing.md },
  // Buttons
  button:       { alignItems: "center", borderRadius: 8, flexDirection: "row", gap: spacing.sm, justifyContent: "center", minHeight: 44, paddingHorizontal: spacing.lg, paddingVertical: spacing.sm },
  btnText:      { fontSize: 14, fontWeight: "800" },
  iconBtn:      { alignItems: "center", borderRadius: 8, height: 40, justifyContent: "center", width: 40 },
  btnDisabled:  { opacity: 0.5 },
  pressed:      { opacity: 0.76 },
  // Field
  field:        { flexGrow: 1, minWidth: 210, gap: 6 },
  label:        { fontSize: 12, fontWeight: "800", textTransform: "uppercase", letterSpacing: 0.4 },
  input:        { borderRadius: 8, borderWidth: 1.5, minHeight: 44, paddingHorizontal: spacing.md, paddingVertical: spacing.sm, fontSize: 14 },
  textarea:     { minHeight: 96, textAlignVertical: "top" },
  // Native chip fallback for SelectBox
  chipWrap:     { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip:         { borderRadius: 8, borderWidth: 1.5, paddingHorizontal: spacing.md, paddingVertical: 10 },
  chipText:     { fontSize: 13, fontWeight: "700" },
  // Toggle
  toggleRow:    { alignItems: "center", flexDirection: "row", gap: spacing.sm, minHeight: 36 },
  toggleTrack:  { borderRadius: 12, height: 22, padding: 2, width: 42 },
  toggleDot:    { backgroundColor: "#FFFFFF", borderRadius: 9, height: 18, width: 18 },
  toggleDotOn:  { transform: [{ translateX: 20 }] },
  toggleLabel:  { fontSize: 14, fontWeight: "700" },
  // Badge
  badge:        { alignSelf: "flex-start", borderRadius: 999, paddingHorizontal: 10, paddingVertical: 4 },
  badgeText:    { fontSize: 12, fontWeight: "800", textTransform: "capitalize" },
  // Stat card
  statCard:     { alignItems: "center", borderRadius: 10, borderWidth: 1, flexDirection: "row", flexGrow: 1, gap: spacing.md, minWidth: 210, padding: spacing.md },
  statIcon:     { alignItems: "center", borderRadius: 8, height: 44, justifyContent: "center", width: 44 },
  statText:     { flex: 1, minWidth: 0 },
  statLabel:    { fontSize: 12, fontWeight: "700" },
  statValue:    { fontSize: 22, fontWeight: "900" },
  // Empty / Loading
  empty:        { alignItems: "center", borderRadius: 8, borderStyle: "dashed", borderWidth: 1.5, gap: spacing.sm, justifyContent: "center", minHeight: 120, padding: spacing.lg },
  emptyText:    { fontSize: 14, fontWeight: "700" },
  loading:      { alignItems: "center", minHeight: 120, justifyContent: "center" },
  // Error
  errorBox:     { alignItems: "center", borderRadius: 8, borderWidth: 1, flexDirection: "row", gap: spacing.sm, padding: spacing.md },
  errorText:    { fontSize: 13, fontWeight: "700", flex: 1 },
  // Data table
  table:        { minWidth: 680 },
  tableHead:    { borderTopLeftRadius: 8, borderTopRightRadius: 8, flexDirection: "row", minHeight: 44 },
  tableHeadCell:{ fontSize: 12, fontWeight: "900", padding: spacing.md, textTransform: "uppercase" },
  tableRow:     { flexDirection: "row", minHeight: 52 },
  tableCell:    { justifyContent: "center", padding: spacing.md },
  // Theme scheme picker cards
  schemeCard:   { alignItems: "center", borderRadius: 8, borderWidth: 2, flexDirection: "row", gap: spacing.sm, paddingHorizontal: spacing.md, paddingVertical: spacing.sm },
  schemeDot:    { borderRadius: 999, height: 14, width: 14 },
  schemeLabel:  { fontSize: 13, fontWeight: "800" },
});
