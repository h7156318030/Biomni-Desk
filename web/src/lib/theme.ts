import type { Prefs } from "@/lib/api";

const KEY = "uiPrefs";

export type Look = Pick<Prefs, "style" | "appearance">;

/** Put the chosen look on <html>; the CSS reads data-style and data-appearance. */
export function applyLook(look: Look): void {
  const root = document.documentElement;
  root.dataset.style = look.style;
  root.dataset.appearance = look.appearance;
  try {
    localStorage.setItem(KEY, JSON.stringify(look));
  } catch {}
}

/** The look used last time, so the page does not flash before the server answers. */
export function cachedLook(): Look | null {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) ?? "null");
    if (v && (v.style === "classic" || v.style === "modern") && ["auto", "light", "dark"].includes(v.appearance)) return v as Look;
  } catch {}
  return null;
}
