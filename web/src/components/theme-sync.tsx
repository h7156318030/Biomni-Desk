"use client";

import { useEffect } from "react";
import { getPrefs } from "@/lib/api";
import { applyLook, cachedLook } from "@/lib/theme";

/** Applies the saved look on every page: from the cache at once, then from the server. Renders nothing. */
export function ThemeSync() {
  useEffect(() => {
    const cached = cachedLook();
    if (cached) applyLook(cached);
    getPrefs()
      .then((v) => applyLook({ style: v.prefs.style, appearance: v.prefs.appearance }))
      .catch(() => {});
  }, []);
  return null;
}
