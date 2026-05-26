import React, { createContext, PropsWithChildren, useCallback, useContext, useMemo, useState } from "react";
import { useColorScheme } from "react-native";

import { ColorMode, Colors, resolveColors, ThemeName } from "@/theme";

type ThemeCtx = {
  colors: Colors;
  themeName: ThemeName;
  colorMode: ColorMode;
  resolvedMode: "light" | "dark";
  isDark: boolean;
  setThemeName: (name: ThemeName) => void;
  setColorMode: (mode: ColorMode) => void;
};

const ThemeContext = createContext<ThemeCtx>({
  colors: resolveColors("default", "light"),
  themeName: "default",
  colorMode: "system",
  resolvedMode: "light",
  isDark: false,
  setThemeName: () => {},
  setColorMode: () => {},
});

function loadPref(key: string, fallback: string): string {
  try {
    if (typeof localStorage !== "undefined") return localStorage.getItem(key) ?? fallback;
  } catch {}
  return fallback;
}

function savePref(key: string, value: string) {
  try {
    if (typeof localStorage !== "undefined") localStorage.setItem(key, value);
  } catch {}
}

export function ThemeProvider({ children }: PropsWithChildren) {
  const sys = useColorScheme();

  const [themeName, setThemeNameRaw] = useState<ThemeName>(
    () => loadPref("qz_theme", "default") as ThemeName
  );
  const [colorMode, setColorModeRaw] = useState<ColorMode>(
    () => loadPref("qz_mode", "system") as ColorMode
  );

  const resolvedMode: "light" | "dark" =
    colorMode === "system" ? (sys === "dark" ? "dark" : "light") : colorMode;
  const isDark = resolvedMode === "dark";

  const colors = useMemo(() => resolveColors(themeName, resolvedMode), [themeName, resolvedMode]);

  const setThemeName = useCallback((name: ThemeName) => {
    setThemeNameRaw(name);
    savePref("qz_theme", name);
  }, []);

  const setColorMode = useCallback((mode: ColorMode) => {
    setColorModeRaw(mode);
    savePref("qz_mode", mode);
  }, []);

  return (
    <ThemeContext.Provider value={{ colors, themeName, colorMode, resolvedMode, isDark, setThemeName, setColorMode }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
