import { useSyncExternalStore } from "react";

export type ThemeChoice = "light" | "system" | "dark";

const KEY = "theme";
const query = window.matchMedia("(prefers-color-scheme: dark)");
const listeners = new Set<() => void>();

function stored(): ThemeChoice {
  try {
    const value = localStorage.getItem(KEY);
    if (value === "light" || value === "dark") return value;
  } catch {
    // Storage can be blocked; fall back to the system setting
  }
  return "system";
}

let choice = stored();

const resolve = (): "light" | "dark" => (choice === "system" ? (query.matches ? "dark" : "light") : choice);

function apply() {
  document.documentElement.dataset.theme = resolve();
  listeners.forEach((listener) => listener());
}

export function setTheme(next: ThemeChoice) {
  choice = next;
  try {
    if (next === "system") localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, next);
  } catch {
    // The choice still applies until the page is closed
  }
  apply();
}

query.addEventListener("change", apply);
apply();

/** Whether the page is currently shown dark (maps and canvases need to know). */
export const isDark = () => resolve() === "dark";

const subscribe = (listener: () => void) => {
  listeners.add(listener);
  return () => listeners.delete(listener);
};

export const useThemeChoice = () => useSyncExternalStore(subscribe, () => choice);
export const useIsDark = () => useSyncExternalStore(subscribe, isDark);
