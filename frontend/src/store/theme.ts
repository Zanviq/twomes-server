import { create } from "zustand";
import { persist } from "zustand/middleware";

export type ThemeMode = "light" | "dark" | "system";

interface ThemeState {
  mode: ThemeMode;
  setMode: (m: ThemeMode) => void;
  apply: () => void;
}

function resolve(mode: ThemeMode): "light" | "dark" {
  if (mode === "system") {
    return window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  }
  return mode;
}

export const useTheme = create<ThemeState>()(
  persist(
    (set, get) => ({
      mode: "system",
      setMode: (mode) => {
        set({ mode });
        document.documentElement.setAttribute("data-theme", resolve(mode));
      },
      apply: () => {
        document.documentElement.setAttribute("data-theme", resolve(get().mode));
      },
    }),
    { name: "tw-theme" },
  ),
);

/** 시스템 테마 변경 구독 (mode가 system일 때 반영). */
export function attachThemeListener() {
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  const handler = () => {
    if (useTheme.getState().mode === "system") useTheme.getState().apply();
  };
  mq.addEventListener("change", handler);
  return () => mq.removeEventListener("change", handler);
}
