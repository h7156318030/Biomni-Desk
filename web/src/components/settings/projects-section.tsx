"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  OPTIONAL_TOOLS,
  createProject,
  deleteProject,
  getProjectSettings,
  listProjects,
  listSkills,
  listUploads,
  putProjectSettings,
  renameProject,
  type Project,
  type ProjectSettings,
  type Skill,
  type Upload,
} from "@/lib/api";
import { Card, ListEditor, SaveBadge, inputCls, useAutosave } from "@/components/settings/ui";
import { tr, useI18n } from "@/lib/i18n";

const MAX_CONTEXT = 4000;

/** Per-project settings: background, standing instructions and skills attached to every new task in the project. */
export function ProjectsSection() {
  const { t } = useI18n();
  const [projects, setProjects] = useState<Project[]>([]);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [current, setCurrent] = useState("quick");
  const [loaded, setLoaded] = useState<{ id: string; value: ProjectSettings } | null>(null);
  const [value, setValue] = useState<ProjectSettings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploads, setUploads] = useState<Upload[]>([]);

  useEffect(() => {
    listUploads().then(setUploads).catch(() => setUploads([]));
  }, []);

  const refresh = useCallback(async () => {
    try {
      const [p, s] = await Promise.all([listProjects(), listSkills()]);
      setProjects(p);
      setSkills(s.filter((x) => x.enabled));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      refresh();
      try {
        const saved = localStorage.getItem("project");
        if (saved && saved !== "all") setCurrent(saved);
      } catch {}
    }, 0);
    return () => clearTimeout(timer);
  }, [refresh]);

  // the chosen project may have been deleted elsewhere
  useEffect(() => {
    if (projects.length && !projects.some((p) => p.id === current)) {
      const timer = setTimeout(() => setCurrent("quick"), 0);
      return () => clearTimeout(timer);
    }
  }, [projects, current]);

  useEffect(() => {
    let alive = true;
    getProjectSettings(current)
      .then((v) => {
        if (!alive) return;
        setLoaded({ id: current, value: v });
        setValue(v);
      })
      .catch((e) => alive && setError(e instanceof Error ? e.message : String(e)));
    return () => {
      alive = false;
      setValue(null);
    };
  }, [current]);

  const save = useCallback((v: ProjectSettings) => putProjectSettings(current, v), [current]);
  const status = useAutosave(value, save);
  const project = useMemo(() => projects.find((p) => p.id === current), [projects, current]);
  const ready = value !== null && loaded?.id === current;

  return (
    <div className="space-y-4">
      <Card
        title={t("Projects")}
        hint={t("Each project can have its own background, instructions and automatically attached skills. They are given to the agent for every new task started in the project.")}
      >
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={current}
            onChange={(e) => {
              setCurrent(e.target.value);
              try {
                localStorage.setItem("project", e.target.value);
              } catch {}
            }}
            aria-label={t("Choose project")}
            className="rounded-lg border border-line bg-paper px-3 py-1.5 text-sm outline-none focus:border-accent"
          >
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.default ? t(p.name) : p.name}
                {p.default ? t(" (default)") : ""} · {t("{count} tasks", { count: p.count })}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={async () => {
              const name = window.prompt(tr("Name of the new project"));
              if (!name?.trim()) return;
              try {
                const p = await createProject(name.trim());
                await refresh();
                setCurrent(p.id);
                setError(null);
              } catch (e) {
                setError(e instanceof Error ? e.message : String(e));
              }
            }}
            className="rounded-lg border border-line px-3 py-1.5 text-sm hover:border-accent"
          >
            ＋ {t("New project")}
          </button>
          {project && !project.default && (
            <>
              <button
                type="button"
                onClick={async () => {
                  const name = window.prompt(tr("Project name"), project.name);
                  if (!name?.trim() || name.trim() === project.name) return;
                  try {
                    setProjects(await renameProject(project.id, name.trim()));
                    setError(null);
                  } catch (e) {
                    setError(e instanceof Error ? e.message : String(e));
                  }
                }}
                className="rounded-lg border border-line px-3 py-1.5 text-sm hover:border-accent"
              >
                {t("Rename")}
              </button>
              <button
                type="button"
                onClick={async () => {
                  if (!window.confirm(tr("Delete project “{name}”? Its tasks are kept and moved back to “Quick task”.", { name: project.name }))) return;
                  try {
                    setProjects(await deleteProject(project.id));
                    setCurrent("quick");
                    try {
                      localStorage.setItem("project", "quick");
                    } catch {}
                  } catch (e) {
                    setError(e instanceof Error ? e.message : String(e));
                  }
                }}
                className="rounded-lg border border-warn/60 px-3 py-1.5 text-sm text-warn"
              >
                {t("Delete project")}
              </button>
            </>
          )}
        </div>
        {error && <p className="text-sm text-warn">{error}</p>}
      </Card>

      {ready && value && (
        <>
          <Card title={t("Project background")} hint={t("Long-term background for the agent: research goals, field, and important constraints.")}>
            <textarea
              value={value.context}
              onChange={(e) => setValue({ ...value, context: e.target.value.slice(0, MAX_CONTEXT) })}
              rows={5}
              aria-label={t("Project background")}
              placeholder={t(
                "e.g. We are designing multi-target CAR-T therapies, focusing on solid tumours, and using public databases as the reference.",
              )}
              className={`${inputCls} resize-y`}
            />
            <p className="text-right text-xs text-soft">
              {value.context.length} / {MAX_CONTEXT}
            </p>
          </Card>

          <Card title={t("Project instructions")} hint={t("Rules that apply only within this project.")}>
            <ListEditor
              items={value.instructions}
              onChange={(v) => setValue({ ...value, instructions: v })}
              placeholder={t("Write a project instruction and press Enter to add it")}
              max={20}
            />
          </Card>

          <Card
            title={t("Skills attached automatically")}
            hint={t("Every new task in this project uses these skills automatically (the same as @-mentioning them each time).")}
          >
            {skills.length === 0 ? (
              <p className="text-sm text-soft">{t("No skills are enabled. Enable or create one on the Skills page.")}</p>
            ) : (
              <ul className="grid gap-2 sm:grid-cols-2">
                {skills.map((s) => {
                  const on = value.skills.includes(s.id);
                  return (
                    <li key={s.id}>
                      <button
                        type="button"
                        aria-pressed={on}
                        onClick={() => setValue({ ...value, skills: on ? value.skills.filter((x) => x !== s.id) : [...value.skills, s.id] })}
                        className={`h-full w-full rounded-lg border p-3 text-left ${on ? "border-accent bg-accent-soft" : "border-line hover:border-accent"}`}
                      >
                        <span className="flex items-center justify-between gap-2 text-sm font-medium">
                          {s.title}
                          {on && <span className="text-accent">✓</span>}
                        </span>
                        <span className="mt-0.5 line-clamp-2 block text-xs text-soft">{s.description}</span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
            <SaveBadge {...status} />
          </Card>

          <Card
            title={t("Files for this project")}
            hint={t("Files uploaded to the Drive. Every task in this project is told where they are, so the agent can open them when they are relevant.")}
          >
            {uploads.length === 0 ? (
              <p className="text-sm text-soft">{t("No uploaded files yet. Upload them from the Drive in the workspace.")}</p>
            ) : (
              <ul className="grid gap-2 sm:grid-cols-2">
                {uploads.map((u) => {
                  const on = (value.files ?? []).includes(u.name);
                  return (
                    <li key={u.name}>
                      <button
                        type="button"
                        aria-pressed={on}
                        onClick={() => setValue({ ...value, files: on ? value.files.filter((x) => x !== u.name) : [...(value.files ?? []), u.name] })}
                        className={`h-full w-full rounded-lg border p-3 text-left text-sm ${on ? "border-accent bg-accent-soft" : "border-line hover:border-accent"}`}
                      >
                        <span className="flex items-center justify-between gap-2">
                          <span className="truncate">{u.name}</span>
                          {on && <span className="text-accent">✓</span>}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </Card>

          <Card
            title={t("Tools switched off for this project")}
            hint={t("A switched-off tool is not offered to the agent in any task of this project.")}
          >
            <ul className="grid gap-2 sm:grid-cols-2">
              {OPTIONAL_TOOLS.map((tool) => {
                const off = (value.tools_off ?? []).includes(tool.id);
                return (
                  <li key={tool.id}>
                    <button
                      type="button"
                      aria-pressed={off}
                      onClick={() => setValue({ ...value, tools_off: off ? value.tools_off.filter((x) => x !== tool.id) : [...(value.tools_off ?? []), tool.id] })}
                      className={`h-full w-full rounded-lg border p-3 text-left text-sm ${off ? "border-warn bg-card" : "border-line hover:border-accent"}`}
                    >
                      {t(tool.label)} {off && <span className="text-warn">· {t("off")}</span>}
                    </button>
                  </li>
                );
              })}
            </ul>
          </Card>
        </>
      )}
    </div>
  );
}
