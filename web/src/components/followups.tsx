"use client";

import { useState } from "react";
import { useI18n } from "@/lib/i18n";

/** "Follow-up questions" as a collapsible list: one row per question, click to ask it. */
export function FollowUps({ items, onPick }: { items: string[]; onPick: (q: string) => void }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(true);
  return (
    <section className="rounded-xl border border-line bg-card">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-4 py-2.5 text-left text-sm text-soft"
        aria-expanded={open}
      >
        <span>💡 {t("Follow-up questions")}</span>
        <span className={`text-xs transition-transform ${open ? "" : "rotate-180"}`}>⌃</span>
      </button>
      {open && (
        <ul className="border-t border-line">
          {items.map((q) => (
            <li key={q} className="border-b border-line last:border-b-0">
              <button type="button" onClick={() => onPick(q)} className="flex w-full gap-2 px-4 py-2 text-left text-sm hover:bg-panel">
                <span className="text-soft">↳</span>
                <span>{q}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
