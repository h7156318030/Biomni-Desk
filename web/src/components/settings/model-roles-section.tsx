"use client";

import { useEffect, useState } from "react";
import { getModels, setModelRoles, type ModelRoles, type ModelsView } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { Card } from "@/components/settings/ui";

type Note = { ok: boolean; text: string };
type RoleId = "planner" | "subagent" | "reviewer" | "image";

const EFFORT_LABEL: Record<string, string> = { minimal: "Minimal", low: "Low", medium: "Medium", high: "High", xhigh: "Extra high", max: "Maximum" };
type IdKey = "planner_model_id" | "subagent_model_id" | "reviewer_model_id" | "image_model_id";
type EffortKey = "planner_effort" | "subagent_effort" | "reviewer_effort";
const MODEL_KEY: Record<RoleId, IdKey> = {
  planner: "planner_model_id",
  subagent: "subagent_model_id",
  reviewer: "reviewer_model_id",
  image: "image_model_id",
};
// the level each role uses; the picture role has none (the image model answers as it is)
const EFFORT_KEY: Partial<Record<RoleId, EffortKey>> = { planner: "planner_effort", subagent: "subagent_effort", reviewer: "reviewer_effort" };
const ROWS: { id: RoleId; label: string; hint: string }[] = [
  { id: "planner", label: "Planning model", hint: "Drafts the plan you approve before a task runs." },
  {
    id: "subagent",
    label: "Sub-agent model",
    hint: "Runs the sub-tasks the main agent hands off with delegate_task. Each sub-task shows as its own card in the session. A lower thinking strength makes sub-tasks faster.",
  },
  { id: "reviewer", label: "Reviewer model", hint: "Checks a finished answer when you press “Review” under it." },
  {
    id: "image",
    label: "Picture model",
    hint: "Reads pictures the agent needs to check (the look_at_image tool). The main model cannot see pictures, so this model must accept image input.",
  },
];

/** The models the helper roles use: planning, sub-agents, the reviewer and pictures. Each has its own model and thinking strength, kept apart
 *  from the main model shown above (which is changed in Models). */
export function ModelRolesSection() {
  const { t } = useI18n();
  const [mv, setMv] = useState<ModelsView | null>(null);
  const [msg, setMsg] = useState<Note | null>(null);

  useEffect(() => {
    let alive = true;
    getModels()
      .then((m) => alive && setMv(m))
      .catch((e) => alive && setMsg({ ok: false, text: e instanceof Error ? e.message : String(e) }));
    return () => {
      alive = false;
    };
  }, []);

  if (!mv) return <p className={`text-sm ${msg ? "text-warn" : "text-soft"}`}>{msg ? msg.text : t("Loading…")}</p>;

  const save = async (patch: Partial<ModelRoles>, ok: string) => {
    try {
      setMv(await setModelRoles(patch));
      setMsg({ ok: true, text: ok });
    } catch (err) {
      setMsg({ ok: false, text: err instanceof Error ? err.message : String(err) });
    }
  };

  const mainLabel = mv.models.find((m) => m.id === mv.active.id)?.label ?? mv.active.model;
  // the levels a model accepts; "same as the main model" uses the main model's levels
  const levelsFor = (id: string | null): string[] => {
    if (!id) return mv.active.effort_options ?? [];
    return mv.models.find((m) => m.id === id)?.effort_options ?? [];
  };
  const selectCls = "mt-1 w-full rounded-md border border-line bg-paper px-2.5 py-1.5 text-sm outline-none focus:border-accent disabled:opacity-50";

  return (
    <div className="space-y-4">
      {msg && (
        <p role="status" className={`rounded-lg border p-2.5 text-sm ${msg.ok ? "border-accent/50 text-accent" : "border-warn/50 text-warn"}`}>
          {msg.text}
        </p>
      )}
      <p className="text-sm text-soft">{t("Main model (set in Models, not changed here): {label}", { label: mainLabel })}</p>

      {ROWS.map((r) => {
        const modelValue = mv.roles[MODEL_KEY[r.id]] ?? "";
        const effortKey = EFFORT_KEY[r.id];
        const levels = effortKey ? levelsFor(mv.roles[MODEL_KEY[r.id]] ?? null) : [];
        return (
          <Card key={r.id} title={t(r.label)} hint={t(r.hint)}>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="text-sm">
                <span className="font-medium">{t("Model")}</span>
                <select
                  value={modelValue}
                  aria-label={t(r.label)}
                  onChange={(e) => save({ [MODEL_KEY[r.id]]: e.target.value || null } as Partial<ModelRoles>, t("Saved. Applies from the next task."))}
                  className={selectCls}
                >
                  <option value="">{t("Same as the main model")}</option>
                  {mv.models
                    .filter((m) => !m.hidden)
                    .map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.label}
                      </option>
                    ))}
                </select>
              </label>
              {effortKey && (
                <label className="text-sm">
                  <span className="font-medium">{t("Thinking strength")}</span>
                  <select
                    value={mv.roles[effortKey] ?? ""}
                    disabled={levels.length === 0}
                    aria-label={t("{role} thinking strength", { role: t(r.label) })}
                    onChange={(e) => save({ [effortKey]: e.target.value || null } as Partial<ModelRoles>, t("Saved. Applies from the next task."))}
                    className={selectCls}
                  >
                    <option value="">{t("Model default")}</option>
                    {levels.map((l) => (
                      <option key={l} value={l}>
                        {t(EFFORT_LABEL[l] ?? l)}
                      </option>
                    ))}
                  </select>
                  {levels.length === 0 && <span className="mt-1 block text-xs text-soft">{t("This model's thinking strength cannot be adjusted.")}</span>}
                </label>
              )}
            </div>
            {r.id === "subagent" && (
              <label className="mt-4 block text-sm">
                <span className="font-medium">{t("Sub-agents that run at once")}</span>
                <select
                  value={mv.roles.subagent_max}
                  aria-label={t("Sub-agents that run at once")}
                  onChange={(e) => save({ subagent_max: Number(e.target.value) }, t("Saved. Applies from the next task."))}
                  className={`${selectCls} sm:w-40`}
                >
                  {[1, 2, 3, 4, 5, 6].map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
                <span className="mt-1 block text-xs text-soft">
                  {t("When the agent hands several independent sub-tasks to sub-agents in one step, this many run side by side; the rest wait their turn.")}
                </span>
              </label>
            )}
          </Card>
        );
      })}
    </div>
  );
}
