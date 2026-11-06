"use client";

import { useEffect, useRef, useState } from "react";
import { useI18n } from "@/lib/i18n";

export type ModeOption = { id: string; label: string; hint: string };

/** How the next task runs: a collapsed choice like the model picker, opening upward to list the modes with what each one does. */
export function ModePicker({ mode, options, disabled, onPick }: { mode: string; options: ModeOption[]; disabled?: boolean; onPick: (id: string) => void }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const current = options.find((o) => o.id === mode) ?? options[0];

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        title={t(current.hint)}
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 rounded-full border border-line bg-card px-3 py-1 text-xs text-soft hover:border-accent disabled:opacity-50"
      >
        <span className="font-medium text-ink">{t(current.label)}</span>
        <span aria-hidden="true">▾</span>
      </button>
      {open && (
        <ul role="listbox" aria-label={t("Task mode")} className="absolute bottom-full left-0 z-20 mb-2 w-72 overflow-hidden rounded-xl border border-line bg-panel py-1 shadow-lg">
          {options.map((o) => (
            <li key={o.id} role="option" aria-selected={o.id === current.id}>
              <button
                type="button"
                onClick={() => {
                  onPick(o.id);
                  setOpen(false);
                }}
                className={`flex w-full flex-col px-3 py-2 text-left hover:bg-accent-soft ${o.id === current.id ? "bg-accent-soft" : ""}`}
              >
                <span className="text-sm font-medium">{t(o.label)}</span>
                <span className="text-xs text-soft">{t(o.hint)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
