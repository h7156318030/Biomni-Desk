"use client";

import { useEffect, useState } from "react";
import { getRuntime, type AgentEvent, type Runtime, type TaskRecord } from "@/lib/api";
import { looksFailed, preview } from "@/components/events";
import { tr, useI18n } from "@/lib/i18n";

export type Run = { n: number; language: string; summary: string; seconds?: number; failed: boolean | null };

/** The code the agent executed in this task, each with how long it took and whether it failed. */
export function runsOf(events: AgentEvent[]): Run[] {
  const runs: Run[] = [];
  for (const e of events) {
    if (e.type === "code") {
      runs.push({ n: runs.length + 1, language: e.language, summary: preview(e.code, 50), seconds: e.elapsed, failed: null });
    } else if (e.type === "observation" && runs.length) {
      const last = runs[runs.length - 1];
      if (last.failed === null) {
        last.failed = looksFailed(e.text);
        last.seconds = e.elapsed ?? last.seconds;
      }
    }
  }
  return runs;
}

function turnSeconds(t: TaskRecord): number {
  const stamps = t.events.map((e) => (e as { ts?: number }).ts).filter((x): x is number => typeof x === "number");
  return stamps.length > 1 ? Math.round(stamps[stamps.length - 1] - stamps[0]) : 0;
}

const TABS = [
  { id: "machine", label: "Machine" },
  { id: "models", label: "Models" },
  { id: "jobs", label: "Jobs" },
  { id: "runs", label: "Runs" },
] as const;
type Tab = (typeof TABS)[number]["id"];

export const EFFORT_LABEL: Record<string, string> = { minimal: "Minimal", low: "Low", medium: "Medium", high: "High", xhigh: "Extra high", max: "Maximum" };

export type ModelCall = Extract<AgentEvent, { type: "llm" }>;

/** What the model calls of a set of events really used: which model, which effort, how many reasoning tokens. */
export function callsOf(events: AgentEvent[]): ModelCall[] {
  return events.filter((e): e is ModelCall => e.type === "llm");
}

export function callSummary(events: AgentEvent[]): string {
  const calls = callsOf(events);
  if (!calls.length) return "";
  const last = calls[calls.length - 1];
  const reasoning = calls.reduce((n, c) => n + (c.reasoning_tokens ?? 0), 0);
  const first = calls[0]; // the level chosen for the task: planning and the first call; later rounds that only read tool results run light
  const effort = first.effort ? tr("reasoning effort {effort}", { effort: tr(EFFORT_LABEL[first.effort] ?? first.effort) }) : "";
  return [last.model, effort, reasoning ? tr("{n} reasoning tokens", { n: reasoning }) : "", calls.length === 1 ? tr("1 call") : tr("{n} calls", { n: calls.length })].filter(Boolean).join(" · ");
}

const STATUS: Record<string, string> = { running: "Running", done: "Done", error: "Error", cancelled: "Stopped", interrupted: "Interrupted" };

/** Where the agent's code runs (the machine), what runs in the background, the tasks, and each code run. */
export function ComputePanel({ events, turns, running }: { events: AgentEvent[]; turns: TaskRecord[]; running: boolean }) {
  const { t } = useI18n();
  const [rt, setRt] = useState<Runtime | null>(null);
  const [tab, setTab] = useState<Tab>("machine");
  useEffect(() => {
    let alive = true;
    getRuntime()
      .then((r) => alive && setRt(r))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);
  const runs = runsOf(events);
  const calls = callsOf(events);
  const total = runs.reduce((n, r) => n + (r.seconds ?? 0), 0);

  return (
    <div className="space-y-3 text-sm">
      <div className="flex gap-1 border-b border-line text-xs" role="tablist" aria-label={t("Compute")}>
        {TABS.map((tb) => (
          <button
            key={tb.id}
            type="button"
            role="tab"
            aria-selected={tab === tb.id}
            onClick={() => setTab(tb.id)}
            className={`-mb-px border-b-2 px-2.5 py-1 ${tab === tb.id ? "border-accent text-ink" : "border-transparent text-soft hover:text-ink"}`}
          >
            {t(tb.label)}
            {tb.id === "runs" && runs.length > 0 && <span className="ml-1 text-soft">{runs.length}</span>}
            {tb.id === "jobs" && turns.length > 0 && <span className="ml-1 text-soft">{turns.length}</span>}
          </button>
        ))}
      </div>

      {tab === "machine" && (
        <div>
          <div className="flex items-center gap-2 rounded-lg border border-line bg-card px-3 py-2">
            <span className={`h-2 w-2 shrink-0 rounded-full bg-accent ${running ? "pulse" : ""}`} />
            <span className="font-medium">{t("This computer")}</span>
            <span className="ml-auto text-xs text-soft">{running ? t("Running") : t("Idle")}</span>
          </div>
          <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
            <dt className="text-soft">{t("System")}</dt>
            <dd>{rt?.platform ?? "…"}</dd>
            <dt className="text-soft">Python</dt>
            <dd>{rt?.python ?? "…"}</dd>
            <dt className="text-soft">{t("Working folder")}</dt>
            <dd className="break-all font-mono">{rt?.workdir ?? "…"}</dd>
            <dt className="text-soft">{t("Data folder")}</dt>
            <dd className="break-all font-mono">{rt?.data_path ?? "…"}</dd>
            <dt className="text-soft">{t("Timeout per run")}</dt>
            <dd>{rt?.timeout_seconds ? t("{n} s", { n: rt.timeout_seconds }) : "…"}</dd>
            <dt className="text-soft">{t("Model")}</dt>
            <dd>{rt?.model ?? "…"}</dd>
          </dl>
          <p className="mt-2 text-xs text-soft">
            {t("Tasks on the website run on cloud machines that scale automatically; the code here runs directly on your computer.")}
          </p>
        </div>
      )}

      {tab === "models" &&
        (calls.length === 0 ? (
          <p className="text-soft">
            {running
              ? t("The model has not responded yet.")
              : t("No model calls recorded for this conversation (only tasks since this start are recorded).")}
          </p>
        ) : (
          <>
            <p className="text-xs text-soft">
              {t("{calls} calls · {reasoning} reasoning tokens · {output} output tokens · {seconds} s in total", {
                calls: calls.length,
                reasoning: calls.reduce((n, c) => n + (c.reasoning_tokens ?? 0), 0),
                output: calls.reduce((n, c) => n + (c.output_tokens ?? 0), 0),
                seconds: calls.reduce((n, c) => n + c.seconds, 0).toFixed(1),
              })}
            </p>
            <p className="text-xs text-soft">{t("“Reasoning effort” is the value the server reports back, not the value we requested.")}</p>
            <ol className="space-y-1">
              {calls.map((c, i) => (
                <li key={i} className="flex items-baseline gap-2 text-xs">
                  <span className="w-4 shrink-0 text-center text-soft">{i + 1}</span>
                  <span className="min-w-0 flex-1 truncate font-mono" title={c.model}>
                    {c.model}
                  </span>
                  <span className="shrink-0 text-soft">
                    {c.effort ? t(EFFORT_LABEL[c.effort] ?? c.effort) : "—"} · {t("reasoning")} {c.reasoning_tokens ?? "—"} · {c.seconds}s
                  </span>
                </li>
              ))}
            </ol>
          </>
        ))}

      {tab === "jobs" &&
        (turns.length === 0 ? (
          <p className="text-soft">{t("This conversation has no tasks yet.")}</p>
        ) : (
          <ol className="space-y-1.5">
            {turns.map((tk, i) => (
              <li key={tk.id} className="flex items-baseline gap-2">
                <span className="w-4 shrink-0 text-center text-xs text-soft">{i + 1}</span>
                <span className="min-w-0 flex-1 truncate" title={tk.prompt}>
                  {tk.prompt}
                </span>
                <span className={`shrink-0 text-xs ${tk.status === "done" ? "text-soft" : tk.status === "running" ? "text-accent" : "text-warn"}`}>
                  {t(STATUS[tk.status] ?? tk.status)}
                  {turnSeconds(tk) > 0 && ` · ${turnSeconds(tk)}s`}
                </span>
              </li>
            ))}
          </ol>
        ))}

      {tab === "runs" &&
        (runs.length === 0 ? (
          <p className="text-soft">{running ? t("The agent has not run any code yet.") : t("This task ran no code.")}</p>
        ) : (
          <>
            <p className="text-xs text-soft">{t("{runs} code runs, {seconds} s in total", { runs: runs.length, seconds: total.toFixed(1) })}</p>
            <ol className="space-y-1">
              {runs.map((r) => (
                <li key={r.n} className="flex items-baseline gap-2">
                  <span
                    className={`w-4 shrink-0 text-center ${r.failed === null ? "pulse text-accent" : r.failed ? "text-warn" : "text-accent"}`}
                    title={r.failed === null ? t("Running") : r.failed ? t("Error") : t("Succeeded")}
                  >
                    {r.failed === null ? "▶" : r.failed ? "✗" : "✓"}
                  </span>
                  <span className="min-w-0 flex-1 truncate font-mono text-xs" title={r.summary}>
                    {r.language} · {r.summary}
                  </span>
                  {r.seconds !== undefined && <span className="shrink-0 text-xs text-soft">{r.seconds.toFixed(1)}s</span>}
                </li>
              ))}
            </ol>
          </>
        ))}
    </div>
  );
}
