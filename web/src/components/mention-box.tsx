"use client";

import { useEffect, useRef, useState } from "react";
import { searchMentions, type Mention } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

const KIND_LABEL: Record<Mention["kind"], string> = { skill: "Skill", tool: "Tool", data: "Dataset", file: "File" };

/** Finds the `@query` the caret is currently inside, if any. */
export function activeMention(text: string, caret: number): { start: number; query: string } | null {
  const before = text.slice(0, caret);
  const m = /(^|\s)@([^\s@]*)$/.exec(before);
  return m ? { start: caret - m[2].length - 1, query: m[2] } : null;
}

export function MentionMenu({
  query,
  onPick,
  onClose,
}: {
  query: string;
  onPick: (m: Mention) => void;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const [items, setItems] = useState<Mention[]>([]);
  const [index, setIndex] = useState(0);
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(true);
  const ref = useRef<HTMLUListElement>(null);

  useEffect(() => {
    let alive = true;
    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const r = await searchMentions(query);
        if (alive) {
          setItems(r);
          setIndex(0);
          setFailed(false);
          setLoading(false);
        }
      } catch {
        if (alive) {
          setFailed(true);
          setLoading(false);
        }
      }
    }, 120);
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [query]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setIndex((i) => Math.min(i + 1, items.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setIndex((i) => Math.max(i - 1, 0));
      } else if ((e.key === "Enter" || e.key === "Tab") && items[index]) {
        e.preventDefault();
        e.stopPropagation();
        onPick(items[index]);
      } else if (e.key === "Enter" && loading) {
        // Results are still coming: swallow Enter so a half-typed "@..." is not sent by accident.
        e.preventDefault();
        e.stopPropagation();
      } else if (e.key === "Enter" || e.key === "Escape") {
        onClose(); // nothing to pick: close the menu; Enter then sends the text as typed
        onClose();
      }
    };
    // capture phase so Enter picks the item instead of sending the message
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [items, index, loading, onPick, onClose]);

  useEffect(() => {
    ref.current?.children[index]?.scrollIntoView({ block: "nearest" });
  }, [index]);

  return (
    <ul ref={ref} className="absolute bottom-full left-0 z-10 mb-2 max-h-64 w-full overflow-y-auto rounded-xl border border-line bg-card p-1 shadow-lg">
      {failed && <li className="px-3 py-2 text-sm text-warn">{t("Could not fetch suggestions. Check that the agent has finished loading.")}</li>}
      {!failed && loading && items.length === 0 && <li className="px-3 py-2 text-sm text-soft">{t("Searching…")}</li>}
      {!failed && !loading && items.length === 0 && <li className="px-3 py-2 text-sm text-soft">{t("No matching skills, tools, datasets or files")}</li>}
      {items.map((m, i) => (
        <li key={`${m.kind}:${m.id}`}>
          <button
            type="button"
            onMouseDown={(e) => {
              e.preventDefault();
              onPick(m);
            }}
            className={`flex w-full items-baseline gap-2 rounded-lg px-3 py-1.5 text-left text-sm ${i === index ? "bg-accent-soft" : ""}`}
          >
            <span className="shrink-0 rounded bg-codebg px-1.5 text-xs text-soft">{t(KIND_LABEL[m.kind])}</span>
            <span className="min-w-0 truncate font-medium">{m.label}</span>
            <span className="min-w-0 flex-1 truncate text-xs text-soft">{m.hint}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}
