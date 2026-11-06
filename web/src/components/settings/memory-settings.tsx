"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  addMemoryNote,
  approveMemoryNote,
  clearWorkLog,
  deleteMemoryNote,
  getMemoryNotes,
  getModels,
  getWorkLog,
  listProjects,
  setModelRoles,
  type MemoryNote,
  type ModelRoles,
  type Project,
  type WorkItem,
  updateMemoryNote,
} from "@/lib/api";
import { Card, Toggle } from "@/components/settings/ui";
import { useI18n } from "@/lib/i18n";

type Patch = { text?: string; category?: string; project_id?: string | null };
const RECALL_OPTIONS = [500, 1000, 1500, 3000, 6000];

/** One remembered note: shows what it is for, and can be edited (text, category, which project) or approved while it is a suggestion. */
function NoteItem({
  n,
  projects,
  scopeName,
  onSave,
  onApprove,
  onDelete,
}: {
  n: MemoryNote;
  projects: Project[];
  scopeName: (n: MemoryNote) => string;
  onSave: (id: string, patch: Patch) => Promise<void>;
  onApprove: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  const { t } = useI18n();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState({ text: n.text, category: n.category, scope: n.project_id ?? "" });
  const pending = n.status === "proposed";
  const origin = n.source === "you" ? t("Added by you") : n.source === "auto" ? t("Suggested after a task") : t("Suggested by the agent");

  if (editing) {
    return (
      <li className="space-y-2 rounded-md border border-accent/50 px-3 py-2">
        <input
          value={draft.text}
          maxLength={300}
          onChange={(e) => setDraft({ ...draft, text: e.target.value })}
          aria-label={t("Note")}
          className="w-full rounded-md border border-line bg-card px-3 py-2 text-sm outline-none focus:border-accent"
        />
        <div className="flex flex-wrap gap-2">
          <input
            value={draft.category}
            maxLength={40}
            onChange={(e) => setDraft({ ...draft, category: e.target.value })}
            aria-label={t("Category")}
            className="w-40 rounded-md border border-line bg-card px-2 py-1.5 text-sm outline-none focus:border-accent"
          />
          <select
            value={draft.scope}
            onChange={(e) => setDraft({ ...draft, scope: e.target.value })}
            aria-label={t("Scope")}
            className="rounded-md border border-line bg-card px-2 py-1.5 text-sm"
          >
            <option value="">{t("All projects")}</option>
            {projects
              .filter((p) => p.id !== "quick")
              .map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
          </select>
        </div>
        <div className="flex gap-3 text-xs">
          <button
            type="button"
            disabled={!draft.text.trim()}
            onClick={async () => {
              await onSave(n.id, { text: draft.text.trim(), category: draft.category.trim() || "General", project_id: draft.scope || null });
              setEditing(false);
            }}
            className="text-accent hover:underline disabled:opacity-40"
          >
            {t("Save")}
          </button>
          <button type="button" onClick={() => setEditing(false)} className="text-soft hover:text-ink">
            {t("Cancel")}
          </button>
        </div>
      </li>
    );
  }

  return (
    <li className={`flex items-start justify-between gap-3 rounded-md border px-3 py-2 ${pending ? "border-dashed border-line" : "border-line"}`}>
      <span className="min-w-0 text-sm">
        {n.text}
        <span className="mt-0.5 block text-xs text-soft">
          {n.category} · {scopeName(n)} · {origin}
        </span>
      </span>
      <span className="flex shrink-0 gap-3 text-xs">
        {pending && (
          <button type="button" onClick={() => onApprove(n.id)} className="text-accent hover:underline">
            {t("Approve")}
          </button>
        )}
        <button type="button" onClick={() => setEditing(true)} className="text-soft hover:text-ink">
          {t("Edit")}
        </button>
        <button type="button" onClick={() => onDelete(n.id)} className="text-soft hover:text-warn">
          {t("Delete")}
        </button>
      </span>
    </li>
  );
}

/** Memory in one place: how it behaves (suggestions after tasks, how much is carried into a task) and the notes themselves. The per-project
 *  switch stays on each project's page. */
export function MemorySettingsSection() {
  const { t } = useI18n();
  const [roles, setRoles] = useState<ModelRoles | null>(null);
  const [notes, setNotes] = useState<MemoryNote[] | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [text, setText] = useState("");
  const [scope, setScope] = useState<string>("");
  const [query, setQuery] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [work, setWork] = useState<WorkItem[] | null>(null);

  const load = useCallback(() => {
    getModels()
      .then((m) => setRoles(m.roles))
      .catch(() => setRoles(null));
    getMemoryNotes()
      .then((r) => setNotes(r.items))
      .catch(() => setNotes([]));
    getWorkLog(15)
      .then((r) => setWork(r.items))
      .catch(() => setWork([]));
    listProjects()
      .then(setProjects)
      .catch(() => setProjects([]));
  }, []);

  const forgetWork = async () => {
    if (!window.confirm(t("Forget the work log of all projects? Each project's notes are kept."))) return;
    try {
      await clearWorkLog();
      setWork([]);
      setMsg(t("Work log cleared."));
    } catch {
      setMsg(t("Could not delete. Please try again."));
    }
  };

  useEffect(() => {
    load();
  }, [load]);

  const saveSetting = async (patch: Partial<ModelRoles>) => {
    try {
      const r = await setModelRoles(patch);
      setRoles(r.roles);
      setMsg(t("Saved. Applies from the next task."));
    } catch (e) {
      setMsg(e instanceof Error ? e.message : t("Could not save. Please try again."));
    }
  };

  const forget = async (id: string) => {
    try {
      const r = await deleteMemoryNote(id);
      setNotes(r.items);
      setMsg(null);
    } catch {
      setMsg(t("Could not delete. Please try again."));
    }
  };

  const approve = async (id: string) => {
    try {
      const r = await approveMemoryNote(id);
      setNotes(r.items);
      setMsg(null);
    } catch {
      setMsg(t("Could not save. Please try again."));
    }
  };

  const save = async (id: string, patch: Patch) => {
    try {
      const r = await updateMemoryNote(id, patch);
      setNotes(r.items);
      setMsg(null);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : t("Could not save. Please try again."));
    }
  };

  const add = async () => {
    if (!text.trim()) return;
    try {
      const r = await addMemoryNote(text.trim(), scope || null);
      setNotes(r.items);
      setText("");
      setMsg(null);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : t("Could not save. Please try again."));
    }
  };

  const scopeName = (n: MemoryNote) => (n.project_id ? projects.find((p) => p.id === n.project_id)?.name ?? n.project_id : t("All projects"));

  // Search runs over the text and the category, as the user types; the list is short enough to filter here.
  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (notes ?? []).filter((n) => !q || `${n.text} ${n.category}`.toLowerCase().includes(q));
  }, [notes, query]);
  const waiting = shown.filter((n) => n.status === "proposed");
  const active = shown.filter((n) => n.status === "approved");

  return (
    <div className="space-y-6">
      <Card title={t("How memory works")} hint={t("Memory is used only for the projects it is switched on for (switch it on each project's page). The notes below are sent with a task only when they match its question.")}>
        {roles === null ? (
          <p className="text-sm text-soft">{t("Loading…")}</p>
        ) : (
          <div className="space-y-4">
            <Toggle
              checked={roles.memory_auto}
              onChange={(v) => saveSetting({ memory_auto: v })}
              label={t("Suggest notes after a task")}
              hint={t("When a task finishes, the agent may suggest lasting facts about you or your project (costs one extra model call). Suggestions wait for your approval below.")}
            />
            <label className="block text-sm">
              <span className="font-medium">{t("How much remembered text a task may carry")}</span>
              <select
                value={roles.memory_recall_chars}
                onChange={(e) => saveSetting({ memory_recall_chars: Number(e.target.value) })}
                aria-label={t("How much remembered text a task may carry")}
                className="mt-1 w-full rounded-md border border-line bg-paper px-2.5 py-1.5 text-sm outline-none focus:border-accent sm:w-48"
              >
                {RECALL_OPTIONS.map((n) => (
                  <option key={n} value={n}>
                    {t("About {count} characters", { count: n })}
                  </option>
                ))}
              </select>
              <span className="mt-1 block text-xs text-soft">
                {t("When there are more notes than this allows, the ones that match the question are used; the rest stay saved.")}
              </span>
            </label>
          </div>
        )}
      </Card>

      <Card
        title={t("What your projects have done")}
        hint={t("Each finished task is recorded here automatically (no model call). Later tasks in the same project get the entries that match their question, so the agent knows what was done before, even in a new conversation.")}
      >
        {work === null ? (
          <p className="text-sm text-soft">{t("Loading…")}</p>
        ) : work.length === 0 ? (
          <p className="text-sm text-soft">{t("Nothing recorded yet. Finished tasks appear here.")}</p>
        ) : (
          <>
            <ul className="space-y-2">
              {work.map((w) => (
                <li key={w.id} className="rounded-md border border-line px-3 py-2 text-sm">
                  <div className="text-xs text-soft">
                    {projects.find((p) => p.id === w.project_id)?.name ?? (w.project_id === "quick" ? t("Quick task") : w.project_id)} ·{" "}
                    {new Date(w.created * 1000).toLocaleString()}
                  </div>
                  <div className="mt-0.5 font-medium">{w.question}</div>
                  <div className="mt-0.5 line-clamp-2 text-xs text-soft">{w.answer}</div>
                </li>
              ))}
            </ul>
            <button type="button" onClick={forgetWork} className="mt-3 text-xs text-soft hover:text-warn">
              {t("Clear the work log")}
            </button>
          </>
        )}
      </Card>

      <Card
        title={t("Things to remember")}
        hint={t("Send a separate message in a conversation starting with “remember: …”, or add one here for all projects or for one project.")}
      >
        <div className="mb-4 flex flex-wrap gap-2">
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            maxLength={300}
            placeholder={t("For example: Species is mouse; use hg38 coordinates")}
            aria-label={t("New note")}
            className="min-w-0 flex-1 rounded-md border border-line bg-card px-3 py-2 text-sm outline-none focus:border-accent"
          />
          <select value={scope} onChange={(e) => setScope(e.target.value)} aria-label={t("Scope")} className="rounded-md border border-line bg-card px-2 py-2 text-sm">
            <option value="">{t("All projects")}</option>
            {projects
              .filter((p) => p.id !== "quick")
              .map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
          </select>
          <button type="button" onClick={add} disabled={!text.trim()} className="rounded-md border border-line px-3 py-2 text-sm hover:border-accent disabled:opacity-50">
            {t("Add")}
          </button>
        </div>

        {notes !== null && notes.length > 0 && (
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("Search notes")}
            aria-label={t("Search notes")}
            className="mb-4 w-full rounded-md border border-line bg-card px-3 py-2 text-sm outline-none focus:border-accent"
          />
        )}

        {notes === null ? (
          <p className="text-sm text-soft">{t("Loading…")}</p>
        ) : (
          <>
            {waiting.length > 0 && (
              <div className="mb-4">
                <p className="mb-2 text-xs font-medium text-soft">{t("Suggested by the agent, waiting for your approval")}</p>
                <ul className="space-y-2">
                  {waiting.map((n) => (
                    <NoteItem key={n.id} n={n} projects={projects} scopeName={scopeName} onSave={save} onApprove={approve} onDelete={forget} />
                  ))}
                </ul>
              </div>
            )}

            {active.length === 0 ? (
              <p className="text-sm text-soft">{query.trim() ? t("No notes match this search.") : t("Nothing remembered yet.")}</p>
            ) : (
              <ul className="space-y-2">
                {active.map((n) => (
                  <NoteItem key={n.id} n={n} projects={projects} scopeName={scopeName} onSave={save} onApprove={approve} onDelete={forget} />
                ))}
              </ul>
            )}
          </>
        )}
      </Card>

      {msg && <p className="text-sm text-warn">{msg}</p>}
    </div>
  );
}
