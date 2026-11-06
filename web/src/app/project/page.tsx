"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  OPTIONAL_TOOLS,
  addMemoryNote,
  approveMemoryNote,
  clearProjectMemory,
  deleteMemoryNote,
  getMemoryNotes,
  getProjectGenerated,
  getProjectSettings,
  getProjectSummary,
  listConversations,
  listProjects,
  putProjectSettings,
  type ConversationSummary,
  type GeneratedFile,
  type MemoryNote,
  type Project,
  type ProjectSettings,
  type ProjectSummary,
} from "@/lib/api";
import { dayBucket } from "@/components/history";
import { useI18n } from "@/lib/i18n";
import { relativeTime } from "@/lib/time";

const TIME_ORDER = ["Today", "Yesterday", "Within 7 days", "Earlier"] as const;
const ALL_MARK = "*";
const groupLabel = (key: string, allLabel: string) => (key.startsWith(ALL_MARK) ? `${allLabel} · ${key.slice(ALL_MARK.length)}` : key);

/**
 * One project, laid out like Claude Science's project page: its sessions by time, its memory (on or off, grouped by category,
 * clearable), what its sessions generated, and its background, files and switched-off tools.
 */
export default function ProjectPage() {
  const { t } = useI18n();
  const [id, setId] = useState<string | null>(null);
  const [project, setProject] = useState<Project | null>(null);
  const [summary, setSummary] = useState<ProjectSummary | null>(null);
  const [settings, setSettings] = useState<ProjectSettings | null>(null);
  const [sessions, setSessions] = useState<ConversationSummary[]>([]);
  const [notes, setNotes] = useState<MemoryNote[]>([]);
  const [generated, setGenerated] = useState<GeneratedFile[]>([]);
  const [text, setText] = useState("");
  const [category, setCategory] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState(0);

  const load = useCallback(async (pid: string) => {
    try {
      const [projects, s, cfg, convs, memo, gen] = await Promise.all([
        listProjects(),
        getProjectSummary(pid),
        getProjectSettings(pid),
        listConversations(),
        getMemoryNotes(),
        getProjectGenerated(pid),
      ]);
      setProject(projects.find((p) => p.id === pid) ?? null);
      setSummary(s);
      setSettings(cfg);
      setSessions(convs.filter((c) => (c.project_id ?? "quick") === pid));
      setNotes(memo.items.filter((n) => n.project_id === null || n.project_id === pid));
      setGenerated(gen.files);
      setNow(Date.now());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    const pid = new URLSearchParams(window.location.search).get("id") || "quick";
    setId(pid);
    load(pid);
  }, [load]);

  const refresh = () => id && load(id);

  const toggleMemory = async () => {
    if (!id || !settings) return;
    setMsg(null);
    try {
      const next = await putProjectSettings(id, { ...settings, memory_on: !settings.memory_on });
      setSettings(next);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    }
  };

  const clearAll = async () => {
    if (!id) return;
    if (!window.confirm(t("Forget everything remembered for this project? Notes for all projects are kept."))) return;
    try {
      await clearProjectMemory(id);
      await refresh();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    }
  };

  const add = async () => {
    if (!id || !text.trim()) return;
    try {
      await addMemoryNote(text.trim(), id, category.trim() || "General");
      setText("");
      await refresh();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    }
  };

  const approve = async (n: MemoryNote) => {
    await approveMemoryNote(n.id);
    await refresh();
  };
  const forget = async (n: MemoryNote) => {
    await deleteMemoryNote(n.id);
    await refresh();
  };

  const groups = useMemo(() => {
    const byCategory = new Map<string, MemoryNote[]>();
    for (const n of notes) {
      const key = n.project_id === null ? `${ALL_MARK}${n.category}` : n.category;  // "*" marks notes that apply to every project
      byCategory.set(key, [...(byCategory.get(key) ?? []), n]);
    }
    return [...byCategory.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [notes]);

  const categories = useMemo(() => [...new Set(notes.map((n) => n.category))], [notes]);

  if (error) return <div className="p-8 text-sm text-warn">{error}</div>;
  if (!project || !summary || !settings) return <div className="p-8 text-sm text-soft">{t("Loading…")}</div>;

  const name = project.default ? t(project.name) : project.name;
  const bucketed = TIME_ORDER.map((label) => ({
    label,
    items: sessions.filter((c) => dayBucket(c.updated, now || c.updated * 1000) === label).sort((a, b) => b.updated - a.updated),
  })).filter((g) => g.items.length > 0);
  const toolLabel = (tool: string) => {
    const hit = OPTIONAL_TOOLS.find((x) => x.id === tool);
    return hit ? t(hit.label) : tool;
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl px-6 py-8">
        <div className="flex items-center justify-between gap-3">
          <Link href="/projects" className="text-xs text-soft hover:text-accent">
            ← {t("All projects")}
          </Link>
          <Link href="/settings?section=projects" className="text-xs text-soft hover:text-accent">
            {t("Edit in Settings")}
          </Link>
        </div>
        <div className="mt-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-[11px] tracking-wider text-soft">{t("Project")}</p>
            <h1 className="font-serif text-3xl font-semibold">{name}</h1>
          </div>
          <button
            type="button"
            onClick={() => {
              if (!id) return;
              try {
                localStorage.setItem("project", id);
              } catch {}
              window.location.href = "/";
            }}
            className="rounded-lg bg-accent px-4 py-2 text-sm text-white"
          >
            ＋ {t("New session here")}
          </button>
        </div>

        <div className="mt-8 grid gap-6 lg:grid-cols-[1.3fr_1fr]">
          <section className="space-y-6">
            <div className="rounded-xl border border-line bg-card">
              <h2 className="border-b border-line px-4 py-3 font-serif text-lg font-semibold">{t("Sessions")}</h2>
              {bucketed.length === 0 ? (
                <p className="p-4 text-sm text-soft">{t("No sessions yet. Start one with “New session here”.")}</p>
              ) : (
                bucketed.map((g) => (
                  <div key={g.label}>
                    <p className="px-4 pt-3 text-[11px] tracking-wider text-soft">{t(g.label)}</p>
                    <ul className="divide-y divide-line">
                      {g.items.map((c) => (
                        <li key={c.id}>
                          <a href={`/?open=${encodeURIComponent(c.id)}`} className="flex items-center justify-between gap-3 px-4 py-2.5 text-sm hover:bg-accent-soft">
                            <span className="truncate">{c.title}</span>
                            <span className="shrink-0 text-xs text-soft">{relativeTime(c.updated)}</span>
                          </a>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))
              )}
            </div>

            <div className="rounded-xl border border-line bg-card">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-3">
                <h2 className="font-serif text-lg font-semibold">{t("Generated files")}</h2>
                <span className="text-xs text-soft">{t("Result files the sessions of this project produced")}</span>
              </div>
              {generated.length === 0 ? (
                <p className="p-4 text-sm text-soft">{t("Nothing generated yet.")}</p>
              ) : (
                <ul className="divide-y divide-line">
                  {generated.map((f) => (
                    <li key={f.path} className="flex items-center justify-between gap-3 px-4 py-2.5 text-sm">
                      <span className="min-w-0">
                        <span className="block truncate">{f.name}</span>
                        <a href={`/?open=${encodeURIComponent(f.session_id)}`} className="block truncate text-xs text-soft hover:text-accent">
                          {f.session_title}
                        </a>
                      </span>
                      <span className="shrink-0 text-xs text-soft">{relativeTime(f.time)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>

          <section className="space-y-6">
            <div className="rounded-xl border border-line bg-card">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-3">
                <div>
                  <h2 className="font-serif text-lg font-semibold">{t("Memory")}</h2>
                  <p className="text-xs text-soft">
                    {settings.memory_on ? t("On: these notes are used in this project’s tasks.") : t("Off: nothing remembered is used in this project’s tasks.")}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    role="switch"
                    aria-checked={settings.memory_on}
                    onClick={toggleMemory}
                    className={`rounded-full border px-3 py-1 text-xs ${settings.memory_on ? "border-accent bg-accent-soft text-accent" : "border-line text-soft"}`}
                  >
                    {settings.memory_on ? t("On") : t("Off")}
                  </button>
                  <button type="button" onClick={clearAll} disabled={notes.length === 0} className="rounded-full border border-line px-3 py-1 text-xs text-soft hover:border-warn disabled:opacity-50">
                    {t("Clear all")}
                  </button>
                </div>
              </div>

              <div className="space-y-3 p-4">
                {groups.length === 0 ? (
                  <p className="text-sm text-soft">{t("Nothing remembered yet.")}</p>
                ) : (
                  groups.map(([cat, items]) => (
                    <div key={cat}>
                      <p className="text-xs font-medium text-soft">
                        {groupLabel(cat, t("All projects"))} <span className="font-normal">· {items.length}</span>
                      </p>
                      <ul className="mt-1 space-y-1">
                        {items.map((n) => (
                          <li key={n.id} className="flex items-start justify-between gap-2 rounded-md border border-line px-2.5 py-1.5 text-sm">
                            <span className="min-w-0">
                              <span className="mr-1 rounded bg-codebg px-1 text-[10px] text-soft">{n.source === "you" ? t("you") : t("auto")}</span>
                              {n.text}
                              {n.status === "proposed" && <span className="ml-1 text-xs text-warn">· {t("waiting for approval")}</span>}
                            </span>
                            <span className="flex shrink-0 gap-2 text-xs">
                              {n.status === "proposed" && (
                                <button type="button" onClick={() => approve(n)} className="text-accent hover:underline">
                                  {t("Approve")}
                                </button>
                              )}
                              <button type="button" onClick={() => forget(n)} className="text-soft hover:text-warn">
                                {t("Delete")}
                              </button>
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))
                )}
              </div>

              <div className="space-y-2 border-t border-line p-4">
                <input
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  maxLength={300}
                  placeholder={t("A fact or preference to remember for this project")}
                  aria-label={t("New note")}
                  className="w-full rounded-md border border-line bg-paper px-2.5 py-1.5 text-sm outline-none focus:border-accent"
                />
                <div className="flex gap-2">
                  <input
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    maxLength={40}
                    list="memory-categories"
                    placeholder={t("Category (General)")}
                    aria-label={t("Category")}
                    className="min-w-0 flex-1 rounded-md border border-line bg-paper px-2.5 py-1.5 text-sm outline-none focus:border-accent"
                  />
                  <datalist id="memory-categories">
                    {categories.map((c) => (
                      <option key={c} value={c} />
                    ))}
                  </datalist>
                  <button type="button" onClick={add} disabled={!text.trim()} className="rounded-md border border-line px-3 py-1.5 text-sm hover:border-accent disabled:opacity-50">
                    {t("Add")}
                  </button>
                </div>
                {msg && <p className="text-xs text-warn">{msg}</p>}
              </div>
            </div>

            <div className="rounded-xl border border-line bg-card p-4 text-sm">
              <h2 className="font-serif text-lg font-semibold">{t("Background and instructions")}</h2>
              {settings.context || settings.instructions.length ? (
                <div className="mt-2 space-y-2">
                  {settings.context && <p className="whitespace-pre-wrap">{settings.context}</p>}
                  {settings.instructions.length > 0 && (
                    <ul className="list-disc space-y-1 pl-5">
                      {settings.instructions.map((x, i) => (
                        <li key={i}>{x}</li>
                      ))}
                    </ul>
                  )}
                </div>
              ) : (
                <p className="mt-2 text-soft">{t("No background or instructions set for this project.")}</p>
              )}
              <h2 className="mt-4 font-serif text-lg font-semibold">{t("Files for this project")}</h2>
              {settings.files.length === 0 ? (
                <p className="mt-2 text-soft">{t("No uploaded files yet. Upload them from the Drive in the workspace.")}</p>
              ) : (
                <ul className="mt-2 space-y-1">
                  {settings.files.map((f) => (
                    <li key={f} className="truncate">
                      {f}
                    </li>
                  ))}
                </ul>
              )}
              <h2 className="mt-4 font-serif text-lg font-semibold">{t("Tools switched off for this project")}</h2>
              {settings.tools_off.length === 0 ? (
                <p className="mt-2 text-soft">{t("All optional tools are on.")}</p>
              ) : (
                <ul className="mt-2 flex flex-wrap gap-2">
                  {settings.tools_off.map((tool) => (
                    <li key={tool} className="rounded-full border border-warn px-3 py-1 text-xs">
                      {toolLabel(tool)}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
