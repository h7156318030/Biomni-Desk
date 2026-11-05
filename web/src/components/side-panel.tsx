"use client";

import { useEffect, useState } from "react";
import type { Source } from "@/lib/citations";
import { useI18n } from "@/lib/i18n";

/** A right-panel block that folds; whether it is open is remembered per block. */
export function SideSection({
  id,
  title,
  count,
  defaultOpen = true,
  children,
}: {
  id: string;
  title: string;
  count?: number;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(defaultOpen);
  useEffect(() => {
    const timer = setTimeout(() => {
      try {
        const v = localStorage.getItem(`side:${id}`);
        if (v !== null) setOpen(v === "1");
      } catch {}
    }, 0);
    return () => clearTimeout(timer);
  }, [id]);
  const toggle = () =>
    setOpen((o) => {
      try {
        localStorage.setItem(`side:${id}`, o ? "0" : "1");
      } catch {}
      return !o;
    });
  return (
    <section className="rounded-xl border border-line bg-card px-3.5 py-3">
      <button
        type="button"
        onClick={toggle}
        aria-expanded={open}
        className={`flex w-full items-center gap-1.5 text-left text-sm font-semibold hover:text-accent ${open ? "mb-2.5" : ""}`}
      >
        <span className={`inline-block text-xs text-soft transition-transform ${open ? "rotate-90" : ""}`}>▸</span>
        {title}
        {count !== undefined && count > 0 && <span className="font-sans text-xs font-normal text-soft">{t("({count})", { count })}</span>}
      </button>
      {open && children}
    </section>
  );
}

export function ProgressBar({ done, total }: { done: number; total: number }) {
  const { t } = useI18n();
  const pct = total ? Math.round((done / total) * 100) : 0;
  return (
    <div className="mb-2" role="progressbar" aria-valuemin={0} aria-valuemax={total} aria-valuenow={done} aria-label={t("Plan progress")}>
      <div className="h-1.5 overflow-hidden rounded-full bg-codebg">
        <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${pct}%` }} />
      </div>
      <p className="mt-1 text-xs text-soft">{t("Done {done} / {total}", { done, total })}</p>
    </div>
  );
}

const KIND_LABEL: Record<Source["kind"], string> = { paper: "Paper", db: "Database", web: "Web" };

/** Every source the tools touched in this conversation, with a kind filter. Raw API endpoints are left out. */
export function SourceList({ ledger }: { ledger: Source[] }) {
  const { t } = useI18n();
  const [kind, setKind] = useState<Source["kind"] | null>(null);
  const rows = ledger.filter((s) => s.reader);
  const kinds = (Object.keys(KIND_LABEL) as Source["kind"][]).filter((k) => rows.some((s) => s.kind === k));
  const shown = rows.filter((s) => !kind || s.kind === kind);
  if (!rows.length) return <p className="text-sm text-soft">{t("Papers, database entries and web pages the tools find will appear here.")}</p>;
  return (
    <div>
      {kinds.length > 1 && (
        <div className="mb-2 flex flex-wrap gap-1.5">
          {[null, ...kinds].map((k) => (
            <button
              key={k ?? "all"}
              type="button"
              aria-pressed={kind === k}
              onClick={() => setKind(k)}
              className={`rounded-full border px-2 py-0.5 text-xs ${kind === k ? "border-accent bg-accent-soft text-accent" : "border-line text-soft hover:border-accent"}`}
            >
              {k ? t(KIND_LABEL[k]) : t("All")}
            </button>
          ))}
        </div>
      )}
      <ul className="max-h-72 space-y-1.5 overflow-y-auto text-sm">
        {shown.map((s) => (
          <li key={s.key} className="flex gap-2">
            <span className="mt-0.5 shrink-0 rounded bg-codebg px-1.5 text-[11px] text-soft">{t(KIND_LABEL[s.kind])}</span>
            <a href={s.href} target="_blank" rel="noreferrer" className="min-w-0 break-words text-accent underline [overflow-wrap:anywhere]">
              {s.title || s.label}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
