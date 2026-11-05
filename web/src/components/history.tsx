"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { relativeTime } from "@/lib/time";
import { useI18n } from "@/lib/i18n";
import type { ConversationSummary, Project } from "@/lib/api";

const PIN_KEY = "pinnedConversations";

function readPins(): string[] {
  try {
    const v = JSON.parse(localStorage.getItem(PIN_KEY) ?? "[]");
    return Array.isArray(v) ? v.filter((x) => typeof x === "string") : [];
  } catch {
    return [];
  }
}

/** Which bucket a timestamp (seconds) falls in, relative to `now` (ms). Exported for tests. */
export function dayBucket(updated: number, now: number): "Today" | "Yesterday" | "Within 7 days" | "Earlier" {
  const d = new Date(now);
  const start = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const t = updated * 1000;
  if (t >= start) return "Today";
  if (t >= start - 86_400_000) return "Yesterday";
  if (t >= start - 6 * 86_400_000) return "Within 7 days";
  return "Earlier";
}

function Highlight({ text, query }: { text: string; query: string }) {
  const q = query.trim();
  const i = q ? text.toLowerCase().indexOf(q.toLowerCase()) : -1;
  if (i < 0) return <>{text}</>;
  return (
    <>
      {text.slice(0, i)}
      <mark className="rounded bg-accent-soft px-0.5 text-inherit">{text.slice(i, i + q.length)}</mark>
      {text.slice(i + q.length)}
    </>
  );
}

export function HistoryList({
  convs,
  activeId,
  query,
  runningId,
  projects = [],
  onOpen,
  onRename,
  onMove,
  onDelete,
}: {
  convs: ConversationSummary[];
  activeId: string | null;
  query: string;
  runningId: string | null;
  projects?: Project[];
  onMove?: (c: ConversationSummary, projectId: string) => void;
  onOpen: (id: string) => void;
  onRename: (c: ConversationSummary, title: string) => void;
  onDelete: (c: ConversationSummary) => void;
}) {
  const { t } = useI18n();
  const [pins, setPins] = useState<string[]>([]);
  const [editing, setEditing] = useState<string | null>(null);
  const [menuFor, setMenuFor] = useState<string | null>(null);
  const [moving, setMoving] = useState(false);
  const [draft, setDraft] = useState("");
  const box = useRef<HTMLInputElement>(null);
  const [now, setNow] = useState(0);

  useEffect(() => {
    const timer = setTimeout(() => {
      setPins(readPins());
      setNow(Date.now());
    }, 0);
    const tick = setInterval(() => setNow(Date.now()), 60_000);
    return () => {
      clearTimeout(timer);
      clearInterval(tick);
    };
  }, []);
  useEffect(() => {
    if (editing) box.current?.select();
  }, [editing]);

  useEffect(() => {
    if (!menuFor) return;
    const close = () => setMenuFor(null);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    document.addEventListener("click", close);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("click", close);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuFor]);

  const togglePin = (id: string) =>
    setPins((prev) => {
      const next = prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id];
      try {
        localStorage.setItem(PIN_KEY, JSON.stringify(next));
      } catch {}
      return next;
    });

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase();
    const rows = convs.filter((c) => !q || c.title.toLowerCase().includes(q));
    const out: { label: string; items: ConversationSummary[] }[] = [];
    const add = (label: string, items: ConversationSummary[]) => items.length && out.push({ label, items });
    add("Pinned", rows.filter((c) => pins.includes(c.id)));
    const rest = rows.filter((c) => !pins.includes(c.id));
    for (const label of ["Today", "Yesterday", "Within 7 days", "Earlier"] as const) {
      add(label, rest.filter((c) => dayBucket(c.updated, now || c.updated * 1000) === label));
    }
    return out;
  }, [convs, query, pins, now]);

  const commit = (c: ConversationSummary) => {
    const title = draft.trim();
    setEditing(null);
    if (title && title !== c.title) onRename(c, title);
  };

  if (groups.length === 0) {
    return <p className="px-2 text-xs text-soft">{convs.length ? t("No matching records") : t("No task history yet")}</p>;
  }

  return (
    <div className="space-y-2">
      {groups.map((g) => (
        <section key={g.label}>
          <h4 className="px-2 pb-0.5 text-[11px] tracking-wider text-soft">{t(g.label)}</h4>
          <ul className="space-y-0.5">
            {g.items.map((c) => (
              <li
                key={c.id}
                className={`group relative flex items-center gap-1 rounded-md px-2 py-1.5 text-sm ${
                  c.id === activeId ? "bg-accent-soft" : "hover:bg-card"
                }`}
              >
                {runningId === c.id || c.status === "running" ? (
                  <span className="pulse h-2 w-2 shrink-0 rounded-full bg-accent" title={t("Running")} />
                ) : c.status === "done" ? (
                  <span className="h-2 w-2 shrink-0 rounded-full bg-accent" title={t("Done")} />
                ) : (
                  <span
                    className="h-2 w-2 shrink-0 rounded-full border border-soft"
                    title={c.status === "error" ? t("Error") : c.status === "cancelled" ? t("Stopped") : t("Not finished")}
                  />
                )}
                {editing === c.id ? (
                  <input
                    ref={box}
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    onBlur={() => commit(c)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") commit(c);
                      if (e.key === "Escape") setEditing(null);
                    }}
                    aria-label={t("Conversation title")}
                    className="min-w-0 flex-1 rounded border border-accent bg-card px-1 py-0 text-sm outline-none"
                  />
                ) : (
                  <button
                    type="button"
                    onClick={() => onOpen(c.id)}
                    onDoubleClick={() => {
                      setDraft(c.title);
                      setEditing(c.id);
                    }}
                    title={`${c.title}\n${t("Double-click to rename")}`}
                    className="min-w-0 flex-1 truncate text-left"
                  >
                    <Highlight text={c.title} query={query} />
                  </button>
                )}
                <span className="shrink-0 text-xs text-soft group-hover:hidden">{relativeTime(c.updated)}</span>
                <button
                  type="button"
                  title={pins.includes(c.id) ? t("Unpin") : t("Pin")}
                  aria-pressed={pins.includes(c.id)}
                  onClick={() => togglePin(c.id)}
                  className={`text-xs ${pins.includes(c.id) ? "text-accent" : "hidden text-soft group-hover:block"}`}
                >
                  {pins.includes(c.id) ? "★" : "☆"}
                </button>
                <button
                  type="button"
                  title={t("More: rename, move, delete")}
                  aria-label={t("More actions")}
                  aria-haspopup="menu"
                  aria-expanded={menuFor === c.id}
                  onClick={(e) => {
                    e.stopPropagation();
                    setMoving(false);
                    setMenuFor((m) => (m === c.id ? null : c.id));
                  }}
                  className="hidden px-0.5 text-sm leading-none text-soft hover:text-accent group-hover:block"
                >
                  ⋯
                </button>
                {menuFor === c.id && (
                  <div role="menu" onClick={(e) => e.stopPropagation()} className="absolute right-1 top-full z-30 mt-1 w-44 overflow-hidden rounded-xl border border-line bg-panel py-1 text-sm shadow-xl">
                    {!moving ? (
                      <>
                        <button
                          type="button"
                          role="menuitem"
                          className="block w-full px-3 py-1.5 text-left hover:bg-accent-soft"
                          onClick={() => {
                            setMenuFor(null);
                            setDraft(c.title);
                            setEditing(c.id);
                          }}
                        >
                          {t("Rename")}
                        </button>
                        {onMove && projects.length > 1 && (
                          <button type="button" role="menuitem" className="flex w-full items-center justify-between px-3 py-1.5 text-left hover:bg-accent-soft" onClick={() => setMoving(true)}>
                            {t("Move to… ")} <span className="text-soft">›</span>
                          </button>
                        )}
                        <button
                          type="button"
                          role="menuitem"
                          className="block w-full px-3 py-1.5 text-left text-warn hover:bg-accent-soft"
                          onClick={() => {
                            setMenuFor(null);
                            onDelete(c);
                          }}
                        >
                          {t("Delete")}
                        </button>
                      </>
                    ) : (
                      <>
                        <button type="button" className="block w-full px-3 py-1 text-left text-xs text-soft hover:text-accent" onClick={() => setMoving(false)}>
                          {t("‹ Back")}
                        </button>
                        {projects.map((p) => (
                          <button
                            key={p.id}
                            type="button"
                            role="menuitem"
                            disabled={p.id === (c.project_id ?? "quick")}
                            className="block w-full truncate px-3 py-1.5 text-left hover:bg-accent-soft disabled:opacity-40"
                            onClick={() => {
                              setMenuFor(null);
                              onMove?.(c, p.id);
                            }}
                          >
                            {p.default ? t(p.name) : p.name}
                          </button>
                        ))}
                      </>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
