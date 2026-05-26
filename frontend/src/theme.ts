export type ThemeName = "default" | "ocean" | "forest" | "rose";
export type ColorMode = "light" | "dark" | "system";

export type Colors = {
  brand: string;
  brandStrong: string;
  brandMuted: string;
  green: string;
  red: string;
  amber: string;
  teal: string;
  violet: string;
  cyan: string;
  navy: string;
  ink: string;
  muted: string;
  faint: string;
  page: string;
  panel: string;
  panelAlt: string;
  line: string;
  subtle: string;
  inputBg: string;
  inputBorder: string;
  navActive: string;
  white: string;
};

const defaultLight: Colors = {
  brand: "#265C8F",
  brandStrong: "#17456F",
  brandMuted: "#E6F0F8",
  green: "#1F8A4C",
  red: "#BE3A34",
  amber: "#B26B12",
  teal: "#117A72",
  violet: "#6B4CA3",
  cyan: "#327E9D",
  navy: "#23334D",
  ink: "#18202F",
  muted: "#647084",
  faint: "#A0ADB8",
  page: "#F7F9FC",
  panel: "#FFFFFF",
  panelAlt: "#F2F5F9",
  line: "#D7DEE8",
  subtle: "#EEF2F6",
  inputBg: "#FBFCFE",
  inputBorder: "#D7DEE8",
  navActive: "#E9F0F8",
  white: "#FFFFFF",
};

const defaultDark: Colors = {
  brand: "#4D9AD6",
  brandStrong: "#7AB8E8",
  brandMuted: "#152438",
  green: "#4CAF72",
  red: "#E06C66",
  amber: "#E0A850",
  teal: "#3AADA4",
  violet: "#9E80CC",
  cyan: "#5BADD0",
  navy: "#8DA4BE",
  ink: "#E8EDF5",
  muted: "#8A9AB0",
  faint: "#4A5A6E",
  page: "#0D1420",
  panel: "#141D2B",
  panelAlt: "#1A2436",
  line: "#243044",
  subtle: "#1A2436",
  inputBg: "#111928",
  inputBorder: "#243044",
  navActive: "#152438",
  white: "#FFFFFF",
};

const oceanLight: Colors = {
  ...defaultLight,
  brand: "#0E7ABF",
  brandStrong: "#085F98",
  brandMuted: "#E0F2FF",
  navActive: "#E0F2FF",
};

const oceanDark: Colors = {
  ...defaultDark,
  brand: "#38BDF8",
  brandStrong: "#7DD3FC",
  brandMuted: "#0A2D44",
  navActive: "#0A2D44",
};

const forestLight: Colors = {
  ...defaultLight,
  brand: "#2D7D46",
  brandStrong: "#1B5C30",
  brandMuted: "#E4F4EA",
  navActive: "#E4F4EA",
};

const forestDark: Colors = {
  ...defaultDark,
  brand: "#4ADE80",
  brandStrong: "#86EFAC",
  brandMuted: "#082918",
  navActive: "#082918",
};

const roseLight: Colors = {
  ...defaultLight,
  brand: "#B23061",
  brandStrong: "#8C1F49",
  brandMuted: "#FBE8EF",
  navActive: "#FBE8EF",
};

const roseDark: Colors = {
  ...defaultDark,
  brand: "#FB7185",
  brandStrong: "#FDA4AF",
  brandMuted: "#3D0A1A",
  navActive: "#3D0A1A",
};

export const THEMES: Record<ThemeName, { label: string; accent: string; light: Colors; dark: Colors }> = {
  default: { label: "Default", accent: "#265C8F", light: defaultLight, dark: defaultDark },
  ocean:   { label: "Ocean",   accent: "#0E7ABF", light: oceanLight,   dark: oceanDark   },
  forest:  { label: "Forest",  accent: "#2D7D46", light: forestLight,  dark: forestDark  },
  rose:    { label: "Rose",    accent: "#B23061", light: roseLight,    dark: roseDark    },
};

export function resolveColors(name: ThemeName, mode: "light" | "dark"): Colors {
  return THEMES[name][mode];
}

export const shadows = {
  panel: {
    shadowColor: "#1B2433",
    shadowOpacity: 0.08,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 4 },
    elevation: 2,
  },
};

export const shadowsDark = {
  panel: {
    shadowColor: "#000000",
    shadowOpacity: 0.28,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 4 },
    elevation: 4,
  },
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
};

// Static fallback kept for backward-compat imports
export const colors = defaultLight;
