"use client";

import { useCallback, useEffect, useState } from "react";
import { createSchedule, deleteSchedule, listSchedules, runScheduleNow, updateSchedule, type Schedule, type ScheduleInput } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

const EMPTY: ScheduleInput = { name: "", prompt: "", kind: "daily", time: "08:00", minutes: 60, enabled: true };

function describe(s: Schedule, t: (text: string) => string): string {
  if (s.schedule.kind === "daily") return `${t("Every day at")} ${s.schedule.time}`;
  return `${t("Every")} ${s.schedule.minutes} ${t("minutes")}`;
}

export default function SchedulesPage() {
  const { t, lang } = useI18n();
  const [jobs, setJobs] = useState<Schedule[]>([]);
  const [form, setForm] = useState<ScheduleInput>(EMPTY);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setJobs(await listSchedules());
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 30000);
    return () => clearInterval(timer);
  }, [refresh]);

  const save = async () => {
    setBusy(true);
    setMessage("");
    try {
      const body: ScheduleInput = { ...form, minutes: form.kind === "every" ? Number(form.minutes) : null, time: form.kind === "daily" ? form.time : null };
      await createSchedule(body);
      setForm(EMPTY);
      await refresh();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const runNow = async (job: Schedule) => {
    setMessage("");
    try {
      const res = await runScheduleNow(job.id);
      setMessage(`${t("Started")} ${job.name}. ${t("The result will appear in the history on the left.")} (${res.conversation_id})`);
      await refresh();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    }
  };

  const toggle = async (job: Schedule) => {
    try {
      await updateSchedule(job.id, {
        name: job.name,
        prompt: job.prompt,
        project_id: job.project_id,
        kind: job.schedule.kind,
        minutes: job.schedule.kind === "every" ? job.schedule.minutes : null,
        time: job.schedule.kind === "daily" ? job.schedule.time : null,
        enabled: !job.enabled,
      });
      await refresh();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    }
  };

  const remove = async (job: Schedule) => {
    if (!window.confirm(t("Delete this schedule? Past results stay in the history."))) return;
    try {
      await deleteSchedule(job.id);
      await refresh();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    }
  };

  const nextText = (s: Schedule) => (s.next_run ? new Date(s.next_run * 1000).toLocaleString(lang === "zh" ? "zh-CN" : "en-US") : "—");

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-4xl px-6 py-8">
        <p className="text-[11px] tracking-wider text-soft">{t("Automation")}</p>
        <h1 className="font-serif text-3xl font-semibold">{t("Schedules")}</h1>
        <p className="mt-1 text-sm text-soft">
          {t("Run a saved question on a schedule. Each run works in auto mode (no questions asked) and its result is saved in the history.")}
        </p>
        <p className="mt-3 rounded-lg border border-line bg-card p-3 text-xs text-soft">
          {t("A schedule runs only while Biomni-Desk is open on this computer. If the agent is busy, the run is retried a minute later.")}
        </p>

        {message && <p className="mt-4 rounded-lg border border-line bg-card p-3 text-sm">{message}</p>}

        <section className="mt-6 rounded-xl border border-line bg-card p-4">
          <h2 className="font-serif text-lg font-semibold">{t("New schedule")}</h2>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <label className="text-sm">
              {t("Name")}
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} maxLength={80} className="mt-1 w-full rounded-lg border border-line bg-paper px-3 py-2 outline-none focus:border-accent" />
            </label>
            <label className="text-sm">
              {t("How often")}
              <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value as "every" | "daily" })} className="mt-1 w-full rounded-lg border border-line bg-paper px-3 py-2 outline-none focus:border-accent">
                <option value="daily">{t("Every day at a set time")}</option>
                <option value="every">{t("Every N minutes")}</option>
              </select>
            </label>
            {form.kind === "daily" ? (
              <label className="text-sm">
                {t("Time (this computer's clock)")}
                <input type="time" value={form.time ?? ""} onChange={(e) => setForm({ ...form, time: e.target.value })} className="mt-1 w-full rounded-lg border border-line bg-paper px-3 py-2 outline-none focus:border-accent" />
              </label>
            ) : (
              <label className="text-sm">
                {t("Minutes between runs (5 to 44640)")}
                <input type="number" min={5} max={44640} value={form.minutes ?? 60} onChange={(e) => setForm({ ...form, minutes: Number(e.target.value) })} className="mt-1 w-full rounded-lg border border-line bg-paper px-3 py-2 outline-none focus:border-accent" />
              </label>
            )}
            <label className="text-sm sm:col-span-2">
              {t("Question to run")}
              <textarea value={form.prompt} onChange={(e) => setForm({ ...form, prompt: e.target.value })} rows={3} maxLength={20000} className="mt-1 w-full rounded-lg border border-line bg-paper px-3 py-2 outline-none focus:border-accent" />
            </label>
          </div>
          <div className="mt-3 flex justify-end">
            <button type="button" disabled={busy || !form.prompt.trim()} onClick={save} className="rounded-lg bg-accent px-4 py-2 text-sm text-white disabled:opacity-50">
              {t("Save schedule")}
            </button>
          </div>
        </section>

        <h2 className="mt-8 font-serif text-lg font-semibold">{t("Your schedules")}</h2>
        {jobs.length === 0 ? (
          <p className="mt-2 text-sm text-soft">{t("No schedules yet.")}</p>
        ) : (
          <ul className="mt-3 grid gap-3">
            {jobs.map((job) => (
              <li key={job.id} className="rounded-xl border border-line bg-card p-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="font-serif text-base font-semibold">{job.name}</p>
                    <p className="mt-0.5 text-xs text-soft">{describe(job, t)} · {t("Next run")}: {job.enabled ? nextText(job) : t("paused")}</p>
                    <p className="mt-1 line-clamp-2 text-sm text-soft">{job.prompt}</p>
                    {job.last_status && <p className="mt-1 text-xs text-soft">{t("Last run")}: {job.last_status}</p>}
                  </div>
                  <div className="flex shrink-0 gap-2 text-xs">
                    <button type="button" onClick={() => runNow(job)} className="rounded-lg border border-line px-3 py-1.5 hover:border-accent">{t("Run now")}</button>
                    <button type="button" onClick={() => toggle(job)} className="rounded-lg border border-line px-3 py-1.5 hover:border-accent">{job.enabled ? t("Pause") : t("Resume")}</button>
                    <button type="button" onClick={() => remove(job)} className="rounded-lg border border-line px-3 py-1.5 text-red-700 hover:border-red-400">{t("Delete")}</button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
