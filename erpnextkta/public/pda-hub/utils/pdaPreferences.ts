export type PdaTheme = "light" | "dark";

const THEME_STORAGE_KEY = "kta_pda_theme";
const SOUND_STORAGE_KEY = "kta_pda_sound";

export function getStoredTheme(): PdaTheme {
  try {
    if (typeof localStorage !== "undefined") {
      return localStorage.getItem(THEME_STORAGE_KEY) === "dark" ? "dark" : "light";
    }
  } catch {
    // Ignore storage access errors in restricted environments.
  }
  return "light";
}

export function setStoredTheme(theme: PdaTheme): void {
  try {
    if (typeof localStorage !== "undefined") {
      localStorage.setItem(THEME_STORAGE_KEY, theme);
    }
  } catch {
    // Ignore storage access errors.
  }
}

export function applyTheme(theme: PdaTheme): void {
  if (typeof document === "undefined") return;
  if (theme === "dark") {
    document.documentElement.setAttribute("data-theme", "dark");
  } else {
    document.documentElement.removeAttribute("data-theme");
  }
}

export function isSoundEnabled(): boolean {
  try {
    if (typeof localStorage !== "undefined") {
      return localStorage.getItem(SOUND_STORAGE_KEY) !== "0";
    }
  } catch {
    // Ignore storage access errors.
  }
  return true;
}

export function setSoundEnabled(enabled: boolean): void {
  try {
    if (typeof localStorage !== "undefined") {
      localStorage.setItem(SOUND_STORAGE_KEY, enabled ? "1" : "0");
    }
  } catch {
    // Ignore storage access errors.
  }
}
