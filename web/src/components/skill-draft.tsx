"use client";

import { useEffect, useState } from "react";
import { createSkill, skillDraft } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

type Draft = { title: string; description: string; category: string; when_to_use: string; avoid: string; body: string };

/** Turns a finished task into a skill: the model drafts it, you read and change it, and only then is it saved to your skills. */
export function SkillDraftDialog({ taskId, onClose, onSaved }: { taskId: string; onClose: () => void; onSaved: (id: string) => void }) {
  const { t } = useI18n();
  const [draft, setDraft] = useState<Draft | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    skillDraft(taskId)
      .then((d) => alive && setDraft(d))
      .catch((e) => alive && setErr(e instanceof Error ? e.message : String(e)));
    return () => {
      alive = false;
    };
  }, [taskId]);

  const save = async () => {
    if (!draft) return;
    setBusy(true);
    setErr(null);
    try {
      const s = await createSkill({ id: draft.title, title: draft.title, description: draft.description, category: draft.category, when_to_use: draft.when_to_use, avoid: draft.avoid, uses: "", chain: "", body: draft.body });
      onSaved(s.id);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const field = (label: string, key: keyof Draft, rows = 1) => (
    <label className="block text-sm">
      <span className="text-xs text-soft">{label}</span>
      {rows > 1 ? (
        <textarea
          value={draft?.[key] ?? ""}
          onChange={(e) => draft && setDraft({ ...draft, [key]: e.target.value })}
          rows={rows}
          className="mt-1 w-full rounded-md border border-line bg-card px-2.5 py-1.5 text-sm outline-none focus:border-accent"
        />
      ) : (
        <input
          value={draft?.[key] ?? ""}
          onChange={(e) => draft && setDraft({ ...draft, [key]: e.target.value })}
          className="mt-1 w-full rounded-md border border-line bg-card px-2.5 py-1.5 text-sm outline-none focus:border-accent"
        />
      )}
    </label>
  );

  return (
    <div role="dialog" aria-modal="true" aria-label={t("Save as a skill")} className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
      <div className="max-h-[90vh] w-full max-w-2xl space-y-3 overflow-y-auto rounded-xl border border-line bg-paper p-5 shadow-lg">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="font-serif text-xl font-semibold">{t("Save as a skill")}</h2>
            <p className="mt-1 text-xs text-soft">{t("The method of this task, written as a reusable skill. Check it and change anything before you save it.")}</p>
          </div>
          <button type="button" onClick={onClose} className="text-sm text-soft hover:text-ink">
            {t("Close")}
          </button>
        </div>
        {!draft && !err && <p className="text-sm text-soft">{t("Drafting the skill…")}</p>}
        {err && <p className="text-sm text-warn">{err}</p>}
        {draft && (
          <>
            {field(t("Name (the skill's id)"), "title")}
            {field(t("What it does"), "description")}
            {field(t("Field"), "category")}
            {field(t("When to use it"), "when_to_use")}
            {field(t("When not to use it"), "avoid")}
            {field(t("Steps"), "body", 12)}
          </>
        )}
        <div className="flex justify-end gap-2 pt-1">
          <button type="button" onClick={onClose} className="rounded-md border border-line px-3 py-1.5 text-sm">
            {t("Cancel")}
          </button>
          <button type="button" onClick={save} disabled={!draft || busy || !draft.title.trim()} className="rounded-md bg-accent px-3 py-1.5 text-sm text-white disabled:opacity-40 dark:text-black">
            {busy ? t("Saving…") : t("Save to my skills")}
          </button>
        </div>
      </div>
    </div>
  );
}
