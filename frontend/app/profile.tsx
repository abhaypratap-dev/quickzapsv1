import React from "react";
import { Text, View } from "react-native";

import { DataTable, Panel, Screen, SelectBox, StatCard, StatusBadge, ThemeSchemePicker } from "@/components/ui";
import { useAuth } from "@/context/AuthContext";
import { useTheme } from "@/context/ThemeContext";
import { money, dateTime } from "@/utils/format";

export default function ProfileScreen() {
  const { user } = useAuth();
  const { colorMode, setColorMode, colors } = useTheme();

  return (
    <Screen title="Profile">
      <StatCard label="Wallet balance" value={money(user?.wallet?.available_balance)} icon="wallet-outline" tone="green" />

      <Panel title="Account">
        <DataTable
          data={user ? [user] : []}
          keyExtractor={(row) => String(row.id)}
          columns={[
            { key: "name",   title: "Name",       render: (row) => <Text style={{ color: colors.ink }}>{`${row.first_name} ${row.last_name}`.trim()}</Text>, width: 180 },
            { key: "mobile", title: "Mobile",     render: (row) => <Text style={{ color: colors.ink }}>{row.mobile}</Text>, width: 130 },
            { key: "email",  title: "Email",      render: (row) => <Text style={{ color: colors.ink }}>{row.email}</Text>, width: 220 },
            { key: "role",   title: "Role",       render: (row) => <Text style={{ color: colors.ink }}>{row.role_name}</Text>, width: 150 },
            { key: "status", title: "Status",     render: (row) => <StatusBadge status={row.status} />, width: 120 },
            { key: "kyc",    title: "KYC",        render: (row) => <StatusBadge status={row.kyc_status} />, width: 150 },
            { key: "last",   title: "Last login", render: (row) => <Text style={{ color: colors.muted }}>{dateTime(row.last_login)}</Text>, width: 190 }
          ]}
        />
      </Panel>

      <Panel title="Appearance">
        <SelectBox
          label="Colour mode"
          value={colorMode}
          options={[
            { label: "Light",  value: "light"  },
            { label: "Dark",   value: "dark"   },
            { label: "System", value: "system" },
          ]}
          onChange={setColorMode}
        />
        <View>
          <Text style={{ color: colors.muted, fontSize: 12, fontWeight: "800", textTransform: "uppercase", letterSpacing: 0.4, marginBottom: 8 }}>
            Colour scheme
          </Text>
          <ThemeSchemePicker />
        </View>
      </Panel>
    </Screen>
  );
}
