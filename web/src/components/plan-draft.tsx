"use client";

import { useState } from "react";
import { useI18n } from "@/lib/i18n";

export type Draft = { prompt: string; questions: string[]; plan: string[] };
export type Approval = { plan: string[]; answers: [string, string][] };

export function PlanDraft({
  draft,
  onApprove,
  onSkip,
  onCancel,
}: {
  draft: Draft;
  onApprove: (a: Approval) => void;
  onSkip: () => void;
  onCancel: () => void;
}) {
  const { t } = useI18n();
  const [steps, setSteps] = useState(draft.plan.length ? draft.plan : [""]);
  const [answers, setAnswers] = useState<string[]>(draft.questions.map(() => ""));

  return (
    <section className="space-y-4 rounded-xl border border-accent/50 bg-card p-5 shadow-sm">
      <div>
        <h3 className="font-serif text-base font-semibold text-accent">{t("Confirm the plan before it runs")}</h3>
        <p className="text-sm text-soft">{t("You can edit, delete or add steps. Once approved, the agent follows this plan.")}</p>
      </div>

      {draft.questions.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-sm font-medium">{t("Information you can add (optional)")}</h4>
          {draft.questions.map((q, i) => (
            <label key={i} className="block text-sm">
              <span className="text-soft">{q}</span>
              <input
                value={answers[i]}
                onChange={(e) => setAnswers((a) => a.map((v, j) => (j === i ? e.target.value : v)))}
                className="mt-1 w-full rounded-md border border-line bg-paper px-2.5 py-1.5 outline-none focus:border-accent"
              />
            </label>
          ))}
        </div>
      )}

      <div className="space-y-1.5">
        <h4 className="text-sm font-medium">{t("Plan steps")}</h4>
        {steps.map((s, i) => (
          <div key={i} className="flex items-center gap-2">
            <span className="w-5 text-right text-sm text-soft">{i + 1}</span>
            <input
              value={s}
              onChange={(e) => setSteps((a) => a.map((v, j) => (j === i ? e.target.value : v)))}
              className="min-w-0 flex-1 rounded-md border border-line bg-paper px-2.5 py-1.5 text-sm outline-none focus:border-accent"
            />
            <button type="button" title={t("Delete this step")} onClick={() => setSteps((a) => a.filter((_, j) => j !== i))} className="text-sm text-soft hover:text-warn">
              ✕
            </button>
          </div>
        ))}
        <button type="button" onClick={() => setSteps((a) => [...a, ""])} className="text-sm text-accent">
          {t("＋ Add step")}
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() =>
            onApprove({
              plan: steps.map((s) => s.trim()).filter(Boolean),
              answers: draft.questions.map((q, i) => [q, answers[i]] as [string, string]),
            })
          }
          className="rounded-lg bg-accent px-4 py-2 text-sm text-white dark:text-black"
        >
          {t("Approve and run")}
        </button>
        <button type="button" onClick={onSkip} className="rounded-lg border border-line px-4 py-2 text-sm hover:border-accent">
          {t("Skip the plan and run directly")}
        </button>
        <button type="button" onClick={onCancel} className="px-2 py-2 text-sm text-soft hover:text-ink">
          {t("Cancel")}
        </button>
      </div>
    </section>
  );
}
