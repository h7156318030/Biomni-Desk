"use client";

import { useEffect, useRef, useState } from "react";
import { useI18n } from "@/lib/i18n";

export type PanelId = "plan" | "results" | "sources" | "compute" | "notes";
export const PANELS: { id: PanelId; label: string }[] = [
  { id: "plan", label: "To-do" },
  { id: "results", label: "Results" },
  { id: "sources", label: "Sources" },
  { id: "compute", label: "Compute" },
  { id: "notes", label: "Notes" },
];

const KEY = "panels";

export function readPanels(): Record<PanelId, boolean> {
  const all = { plan: true, results: true, sources: true, compute: true, notes: true };
  try {
    const v = JSON.parse(localStorage.getItem(KEY) ?? "{}");
    for (const p of PANELS) if (v[p.id] === false) all[p.id] = false;
  } catch {}
  return all;
}

export function writePanels(v: Record<PanelId, boolean>) {
  try {
    localStorage.setItem(KEY, JSON.stringify(v));
  } catch {}
}

/** "Layout": which right-hand panels are shown, one switch each. */
export function LayoutMenu({ value, onChange }: { value: Record<PanelId, boolean>; onChange: (v: Record<PanelId, boolean>) => void }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={box} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        title={t("Layout: choose which right-hand panels to show")}
        className="rounded-md border border-line px-2 py-0.5 text-xs text-soft hover:border-accent"
      >
        {t("Layout")}
      </button>
      {open && (
        <div role="menu" className="absolute right-0 top-full z-30 mt-1 w-48 rounded-xl border border-line bg-panel p-2 shadow-xl">
          <p className="px-2 pb-1 text-xs font-medium">{t("Layout settings")}</p>
          {PANELS.map((p) => (
            <label key={p.id} className="flex cursor-pointer items-center justify-between gap-3 rounded-md px-2 py-1.5 text-sm hover:bg-card">
              {t(p.label)}
              <button
                type="button"
                role="switch"
                aria-checked={value[p.id]}
                aria-label={t(p.label)}
                onClick={() => {
                  const next = { ...value, [p.id]: !value[p.id] };
                  onChange(next);
                  writePanels(next);
                }}
                className={`relative h-5 w-9 shrink-0 rounded-full transition-colors ${value[p.id] ? "bg-accent" : "bg-line"}`}
              >
                <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-all ${value[p.id] ? "left-[1.15rem]" : "left-0.5"}`} />
              </button>
            </label>
          ))}
        </div>
      )}
    </div>
  );
}
