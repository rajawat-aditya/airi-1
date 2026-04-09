"use client";
import { webLightTheme, webDarkTheme } from "@fluentui/react-components";
import { useTheme } from "./useTheme";

const WINDOWS_BLUE_TOKENS = {
  colorBrandBackground: '#0078D4',
  colorBrandBackgroundHover: '#106EBE',
  colorBrandBackgroundPressed: '#005A9E',
  colorBrandForeground1: '#0078D4',
  colorBrandStroke1: '#0078D4',
  colorBrandStroke2: '#106EBE',
};

export function buildCustomTheme(themeMode) {
  const base = themeMode === "Day" ? webLightTheme : webDarkTheme;
  return { ...base, ...WINDOWS_BLUE_TOKENS };
}

export function useFluentTheme() {
  const context = useTheme();
  const theme = context?.theme ?? "Night";
  return buildCustomTheme(theme);
}
