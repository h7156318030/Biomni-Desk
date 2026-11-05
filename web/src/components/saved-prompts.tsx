"use client";

import { useCallback, useEffect, useState } from "react";
import { useI18n } from "@/lib/i18n";

const KEY = "savedPrompts";
const MAX = 30;

function read(): string[] {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) ?? "[]");
    return Array.isArray(v) ? v.filter((x) => typeof x === "string" && x.trim()) : [];
  } catch {
    return [];
  }
}

/** Questions the user starred, newest first, kept in this browser. */
export function useSavedPrompts() {
  const [items, setItems] = useState<string[]>([]);
  useEffect(() => {
    const timer = setTimeout(() => setItems(read()), 0);
    return () => clearTimeout(timer);
  }, []);
  const write = useCallback((next: string[]) => {
    setItems(next);
    try {
      localStorage.setItem(KEY, JSON.stringify(next));
    } catch {}
  }, []);
  const toggle = useCallback(
    (text: string) => {
      const t = text.trim();
      if (!t) return;
      const cur = read();
      write(cur.includes(t) ? cur.filter((x) => x !== t) : [t, ...cur].slice(0, MAX));
    },
    [write],
  );
  const remove = useCallback((text: string) => write(read().filter((x) => x !== text)), [write]);
  return { items, toggle, remove };
}

export function SavedPrompts({ items, onPick, onRemove }: { items: string[]; onPick: (p: string) => void; onRemove: (p: string) => void }) {
  const { t } = useI18n();
  if (!items.length) return null;
  return (
    <section className="mx-auto mt-8 w-full max-w-3xl text-left">
      <h3 className="mb-2 text-xs font-medium tracking-wider text-soft">{t("My prompts")}</h3>
      <ul className="space-y-1.5">
        {items.slice(0, 5).map((p) => (
          <li key={p} className="group flex items-center gap-2 rounded-lg border border-line bg-card px-3 py-2 text-sm hover:border-accent">
            <button type="button" onClick={() => onPick(p)} className="min-w-0 flex-1 truncate text-left" title={p}>
              {p}
            </button>
            <button
              type="button"
              onClick={() => onRemove(p)}
              title={t("Remove")}
              aria-label={t("Remove this prompt")}
              className="hidden text-xs text-soft hover:text-warn group-hover:block"
            >
              ✕
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
