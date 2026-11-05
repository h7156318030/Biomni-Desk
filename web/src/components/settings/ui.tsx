"use client";

import { useEffect, useRef, useState } from "react";
import { useI18n } from "@/lib/i18n";

export const inputCls = "w-full rounded-md border border-line bg-paper px-2.5 py-1.5 text-sm outline-none focus:border-accent";

export function Card({ title, hint, children }: { title?: string; hint?: string; children: React.ReactNode }) {
  return (
    <section className="space-y-4 rounded-xl border border-line bg-card p-5">
      {title && (
        <div>
          <h2 className="font-serif text-lg font-semibold">{title}</h2>
          {hint && <p className="mt-0.5 text-xs text-soft">{hint}</p>}
        </div>
      )}
      {children}
    </section>
  );
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <div className="text-sm font-medium">{label}</div>
      {hint && <p className="text-xs text-soft">{hint}</p>}
      {children}
    </div>
  );
}

export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
}: {
  value: T;
  options: { id: T; label: string; hint?: string }[];
  onChange: (v: T) => void;
  label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex flex-wrap gap-1 rounded-lg bg-codebg p-1">
      {options.map((o) => (
        <button
          key={o.id}
          type="button"
          role="radio"
          aria-checked={value === o.id}
          title={o.hint}
          onClick={() => onChange(o.id)}
          className={`rounded-md px-3.5 py-1.5 text-sm ${value === o.id ? "bg-accent-soft font-medium text-accent shadow-sm" : "text-soft hover:text-ink"}`}
        >
          {value === o.id && <span className="mr-1">✓</span>}
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Toggle({ checked, onChange, label, hint, badge }: { checked: boolean; onChange: (v: boolean) => void; label: string; hint?: string; badge?: string }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div className="min-w-0">
        <div className="flex items-center gap-2 text-sm font-medium">
          {label}
          {badge && <span className="rounded bg-codebg px-1.5 text-[11px] font-normal text-soft">{badge}</span>}
        </div>
        {hint && <p className="mt-0.5 text-xs text-soft">{hint}</p>}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        onClick={() => onChange(!checked)}
        className={`relative mt-0.5 h-5 w-9 shrink-0 rounded-full transition-colors ${checked ? "bg-accent" : "bg-line"}`}
      >
        <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-all ${checked ? "left-[1.15rem]" : "left-0.5"}`} />
      </button>
    </div>
  );
}

/** A list of short texts the user can add to and remove from (custom instructions). */
export function ListEditor({ items, onChange, placeholder, max, maxChars = 500 }: { items: string[]; onChange: (v: string[]) => void; placeholder: string; max: number; maxChars?: number }) {
  const { t } = useI18n();
  const [draft, setDraft] = useState("");
  const add = () => {
    const text = draft.trim();
    if (!text || items.includes(text) || items.length >= max) return;
    onChange([...items, text.slice(0, maxChars)]);
    setDraft("");
  };
  return (
    <div className="space-y-2">
      {items.length === 0 ? (
        <p className="text-xs text-soft">{t("Nothing yet. Write one below and press Enter to add it.")}</p>
      ) : (
        <ol className="space-y-1.5">
          {items.map((item, i) => (
            <li key={item} className="flex items-start gap-2 rounded-lg border border-line bg-paper px-3 py-2 text-sm">
              <span className="mt-0.5 w-4 shrink-0 text-xs text-soft">{i + 1}.</span>
              <span className="min-w-0 flex-1 whitespace-pre-wrap break-words">{item}</span>
              <button
                type="button"
                onClick={() => onChange(items.filter((x) => x !== item))}
                aria-label={t("Delete item {n}", { n: i + 1 })}
                title={t("Delete")}
                className="shrink-0 text-soft hover:text-warn"
              >
                ✕
              </button>
            </li>
          ))}
        </ol>
      )}
      <div className="flex gap-2">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.nativeEvent.isComposing) {
              e.preventDefault();
              add();
            }
          }}
          maxLength={maxChars}
          placeholder={items.length >= max ? t("Up to {max} items", { max }) : placeholder}
          disabled={items.length >= max}
          aria-label={placeholder}
          className={inputCls}
        />
        <button
          type="button"
          onClick={add}
          disabled={!draft.trim() || items.length >= max}
          className="shrink-0 rounded-md border border-line px-3 text-sm hover:border-accent disabled:opacity-40"
        >
          {t("Add")}
        </button>
      </div>
    </div>
  );
}

export type SaveState = "idle" | "saving" | "saved" | "error";

/** Calls `save(value)` shortly after `value` stops changing (not for the first value), and reports how it went. */
export function useAutosave<T>(value: T | null, save: (v: T) => Promise<unknown>, delay = 700): { state: SaveState; error: string | null } {
  const [state, setState] = useState<SaveState>("idle");
  const [error, setError] = useState<string | null>(null);
  const first = useRef(true);
  const latest = useRef(save);
  useEffect(() => {
    latest.current = save;
  });
  useEffect(() => {
    if (value === null) {
      first.current = true;
      return;
    }
    if (first.current) {
      first.current = false;
      return;
    }
    const t0 = setTimeout(() => setState("saving"), 0);
    const timer = setTimeout(async () => {
      try {
        await latest.current(value);
        setState("saved");
        setError(null);
      } catch (e) {
        setState("error");
        setError(e instanceof Error ? e.message : String(e));
      }
    }, delay);
    return () => {
      clearTimeout(t0);
      clearTimeout(timer);
    };
  }, [value, delay]);
  return { state, error };
}

export function SaveBadge({ state, error }: { state: SaveState; error: string | null }) {
  const { t } = useI18n();
  return (
    <p className={`text-xs ${state === "error" ? "text-warn" : "text-soft"}`} role="status" aria-live="polite">
      {state === "saving"
        ? t("Saving…")
        : state === "saved"
          ? t("Saved automatically")
          : state === "error"
            ? t("Save failed: {error}", { error: error ?? "" })
            : t("Changes are saved automatically")}
    </p>
  );
}
