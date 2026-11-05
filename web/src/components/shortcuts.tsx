"use client";

import { useEffect } from "react";
import { useI18n } from "@/lib/i18n";

export const SHORTCUTS: { keys: string; what: string }[] = [
  { keys: "Ctrl K", what: "New task" },
  { keys: "/", what: "Back to the input box" },
  { keys: "Ctrl B", what: "Show / hide left column" },
  { keys: "Ctrl \\", what: "Show / hide right column" },
  { keys: "Enter", what: "Send (Shift Enter for a new line)" },
  { keys: "?", what: "Open this list" },
  { keys: "Esc", what: "Close pop-ups" },
];

/** True when the user is typing somewhere, so single-key shortcuts must not fire. */
export function isTyping(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  if (!el) return false;
  return el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable;
}

export function ShortcutHelp({ onClose }: { onClose: () => void }) {
  const { t } = useI18n();
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/30 p-4" onClick={onClose} role="presentation">
      <div
        role="dialog"
        aria-label={t("Keyboard shortcuts")}
        className="w-full max-w-sm rounded-xl border border-line bg-panel p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-serif text-lg font-semibold">{t("Keyboard shortcuts")}</h2>
          <button type="button" onClick={onClose} aria-label={t("Close")} className="text-soft hover:text-accent">
            ✕
          </button>
        </div>
        <ul className="space-y-2 text-sm">
          {SHORTCUTS.map((s) => (
            <li key={s.keys} className="flex items-center justify-between gap-4">
              <span>{t(s.what)}</span>
              <kbd className="rounded-md border border-line bg-card px-2 py-0.5 font-mono text-xs">{s.keys}</kbd>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
