"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { createProject, listConversations, listProjects, type ConversationSummary, type Project } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { relativeTime } from "@/lib/time";

/** All projects, with how many sessions each holds and when it was last used, and the most recent sessions across them. */
export default function ProjectsPage() {
  const { t } = useI18n();
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [convs, setConvs] = useState<ConversationSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      const [p, c] = await Promise.all([listProjects(), listConversations()]);
      setProjects(p);
      setConvs(c);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  useEffect(() => {
    load();
  }, []);

  const lastUsed = useMemo(() => {
    const out: Record<string, number> = {};
    for (const c of convs) {
      const pid = c.project_id ?? "quick";
      out[pid] = Math.max(out[pid] ?? 0, c.updated);
    }
    return out;
  }, [convs]);

  const titleOf = (pid: string) => {
    const p = projects?.find((x) => x.id === pid);
    return p ? (p.default ? t(p.name) : p.name) : pid;
  };

  const newProject = async () => {
    const name = window.prompt(t("Name for the new project"));
    if (!name?.trim()) return;
    try {
      await createProject(name.trim());
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl px-6 py-8">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-[11px] tracking-wider text-soft">{t("Workspace")}</p>
            <h1 className="font-serif text-3xl font-semibold">{t("Projects")}</h1>
          </div>
          <button type="button" onClick={newProject} className="rounded-lg bg-accent px-4 py-2 text-sm text-white">
            ＋ {t("New project")}
          </button>
        </div>
        <p className="mt-2 text-sm text-soft">
          {t("A project groups its sessions, its files, what it generated, and what the agent should remember for it.")}
        </p>
        {error && <p className="mt-3 text-sm text-warn">{error}</p>}

        <div className="mt-6 grid gap-6 lg:grid-cols-[1.4fr_1fr]">
          <section className="rounded-xl border border-line bg-card">
            <h2 className="border-b border-line px-4 py-3 font-serif text-lg font-semibold">{t("Projects")}</h2>
            {projects === null ? (
              <p className="p-4 text-sm text-soft">{t("Loading…")}</p>
            ) : (
              <ul className="divide-y divide-line">
                {projects.map((p) => (
                  <li key={p.id}>
                    <Link href={`/project?id=${encodeURIComponent(p.id)}`} className="flex items-center justify-between gap-3 px-4 py-3 hover:bg-accent-soft">
                      <span className="flex min-w-0 items-center gap-2">
                        <span className="truncate font-medium">{p.default ? t(p.name) : p.name}</span>
                        {p.default && <span className="rounded bg-codebg px-1.5 text-[11px] text-soft">{t("Default")}</span>}
                      </span>
                      <span className="flex shrink-0 gap-4 text-xs text-soft">
                        <span>
                          {p.count} {p.count === 1 ? t("session") : t("sessions")}
                        </span>
                        <span className="w-14 text-right">{lastUsed[p.id] ? relativeTime(lastUsed[p.id]) : "—"}</span>
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="rounded-xl border border-line bg-card">
            <h2 className="border-b border-line px-4 py-3 font-serif text-lg font-semibold">{t("Recent sessions")}</h2>
            {convs.length === 0 ? (
              <p className="p-4 text-sm text-soft">{t("No sessions yet.")}</p>
            ) : (
              <ul className="divide-y divide-line">
                {[...convs]
                  .sort((a, b) => b.updated - a.updated)
                  .slice(0, 12)
                  .map((c) => (
                    <li key={c.id}>
                      <a href={`/?open=${encodeURIComponent(c.id)}`} className="block px-4 py-2.5 hover:bg-accent-soft">
                        <span className="flex items-center justify-between gap-3">
                          <span className="truncate text-sm">{c.title}</span>
                          <span className="shrink-0 text-xs text-soft">{relativeTime(c.updated)}</span>
                        </span>
                        <span className="block truncate text-xs text-soft">{titleOf(c.project_id ?? "quick")}</span>
                      </a>
                    </li>
                  ))}
              </ul>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
