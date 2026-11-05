"use client";

import { useCallback, useEffect, useState } from "react";
import { ChatGPTLogin } from "@/components/chatgpt-login";
import {
  clearAllData,
  downloadExport,
  getConnections,
  getDataInfo,
  getHealth,
  getSettings,
  getUsage,
  putSettings,
  type Connections,
  type DataInfo,
  type Health,
  type SettingsView,
  type Usage,
} from "@/lib/api";
import { formatSize } from "@/components/results-panel";
import { useI18n } from "@/lib/i18n";
import { Card, Toggle, inputCls } from "@/components/settings/ui";

/** Tool retrieval and licence mode: these rebuild the agent, so they have an explicit save. */
export function AgentSection() {
  const { t } = useI18n();
  const [view, setView] = useState<SettingsView | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [retriever, setRetriever] = useState(true);
  const [commercial, setCommercial] = useState(false);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    let alive = true;
    getSettings()
      .then((v) => {
        if (!alive) return;
        setView(v);
        setRetriever(v.values.use_tool_retriever);
        setCommercial(v.values.commercial_mode);
      })
      .catch((e) => alive && setMsg({ ok: false, text: e instanceof Error ? e.message : String(e) }));
    const poll = () =>
      getHealth()
        .then((h) => alive && setHealth(h))
        .catch(() => {});
    poll();
    const i = setInterval(poll, 3000);
    return () => {
      alive = false;
      clearInterval(i);
    };
  }, []);

  const changed = !!view && (retriever !== view.values.use_tool_retriever || commercial !== view.values.commercial_mode);
  const status = !health
    ? t("Connecting…")
    : health.agent_error
      ? t("Failed to load: {error}", { error: health.agent_error })
      : health.agent_ready
        ? t("Agent ready")
        : t("Agent loading…");

  const save = async () => {
    setSaving(true);
    setMsg(null);
    try {
      setView(await putSettings({ use_tool_retriever: retriever, commercial_mode: commercial }));
      setMsg({ ok: true, text: t("Saved. The agent is reloading; do not start a task until it finishes.") });
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : String(e) });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card title={t("Agent")} hint={t("Current status: {status}", { status })}>
      <Toggle
        checked={retriever}
        onChange={setRetriever}
        label={t("Choose relevant tools before acting")}
        hint={t("When on, each task makes one extra model call, but the prompt is shorter and more accurate. When off, the descriptions of all tools go into the prompt, which can be very long.")}
      />
      <Toggle
        checked={commercial}
        onChange={setCommercial}
        label={t("Commercial mode")}
        hint={t("When on, datasets marked for non-commercial use upstream are excluded. Turn this on before any commercial use, and check each data source's licence yourself.")}
      />
      {msg && (
        <p role="status" className={`rounded-lg border p-3 text-sm ${msg.ok ? "border-accent/50 text-accent" : "border-warn/50 text-warn"}`}>
          {msg.text}
        </p>
      )}
      <button type="button" onClick={save} disabled={saving || !changed || !!health?.busy} className="rounded-lg bg-accent px-5 py-2 text-sm text-white disabled:opacity-40 dark:text-black">
        {saving ? t("Saving…") : t("Save and reload agent")}
      </button>
      {health?.busy && <p className="text-xs text-warn">{t("A task is running. You can save when it finishes.")}</p>}
    </Card>
  );
}

export function UsageSection() {
  const { t } = useI18n();
  const [u, setU] = useState<Usage | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    getUsage()
      .then((v) => alive && setU(v))
      .catch((e) => alive && setError(e instanceof Error ? e.message : String(e)));
    return () => {
      alive = false;
    };
  }, []);
  if (!u) return <p className={`text-sm ${error ? "text-warn" : "text-soft"}`}>{error ?? t("Loading…")}</p>;
  const max = Math.max(1, ...u.series.map((d) => d.tasks));
  const today = u.series[u.series.length - 1]?.tasks ?? 0;
  const stat = (label: string, value: string) => (
    <div className="rounded-lg border border-line p-3">
      <div className="text-xs text-soft">{label}</div>
      <div className="mt-0.5 font-serif text-2xl font-semibold">{value}</div>
    </div>
  );
  return (
    <Card
      title={t("Usage")}
      hint={t("Tasks and code runs recorded on this computer. ChatGPT quota is counted by OpenAI and is not visible here; for OpenRouter spending, check its website.")}
    >
      <div className="grid gap-3 sm:grid-cols-4">
        {stat(t("Tasks today"), String(today))}
        {stat(t("Total tasks"), String(u.tasks_total))}
        {stat(t("Code runs"), t("{n} segments", { n: u.code_runs }))}
        {stat(t("Total code time"), t("{n} s", { n: u.code_seconds }))}
      </div>
      <div>
        <p className="mb-1 text-xs text-soft">{t("Tasks per day, last 14 days")}</p>
        <div className="flex h-28 items-end gap-1" role="img" aria-label={t("Tasks per day, last 14 days")}>
          {u.series.map((d) => (
            <div key={d.day} className="flex h-full flex-1 flex-col items-center justify-end gap-1" title={t("{day}: {tasks} tasks", { day: d.day, tasks: d.tasks })}>
              <span className="text-[10px] text-soft">{d.tasks || ""}</span>
              <span className="w-full rounded-sm bg-accent" style={{ height: `${Math.max(d.tasks ? 6 : 2, (d.tasks / max) * 80)}%`, opacity: d.tasks ? 1 : 0.25 }} />
              <span className="text-[10px] text-soft">{d.day.slice(8)}</span>
            </div>
          ))}
        </div>
      </div>
      <p className="text-xs text-soft">
        {t("Done {done} · Error {error} · Stopped {stopped} · Interrupted {interrupted}", {
          done: u.status.done ?? 0,
          error: u.status.error ?? 0,
          stopped: u.status.cancelled ?? 0,
          interrupted: u.status.interrupted ?? 0,
        })}
      </p>
    </Card>
  );
}

export function ConnectionsSection() {
  const { t } = useI18n();
  const [c, setC] = useState<Connections | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    getConnections()
      .then((v) => alive && setC(v))
      .catch((e) => alive && setError(e instanceof Error ? e.message : String(e)));
    return () => {
      alive = false;
    };
  }, []);
  const row = (label: string, ok: boolean, detail: string) => (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-line p-3 text-sm">
      <div className="min-w-0">
        <div className="font-medium">{label}</div>
        <div className="truncate text-xs text-soft">{detail}</div>
      </div>
      <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs ${ok ? "bg-accent-soft text-accent" : "bg-codebg text-soft"}`}>
        {ok ? t("Connected") : t("Not connected")}
      </span>
    </div>
  );
  return (
    <div className="space-y-4">
      <Card title={t("Connections")} hint={t("Where this workspace connects. No keys are shown here.")}>
        {error && <p className="text-sm text-warn">{error}</p>}
        {c && (
          <div className="space-y-2">
            {row(
              "ChatGPT",
              c.chatgpt.logged_in,
              c.chatgpt.logged_in ? t("gpt-6-luna directly, without Codex's own tools") : t("Not signed in: sign in once below"),
            )}
            {c.providers.map((p) => row(p.name, p.ready, p.ready ? (p.local ? t("Local") : p.base_url) : t("No key: add it under Settings → Models")))}
          </div>
        )}
        <ChatGPTLogin />
      </Card>
      {c && (
        <Card title={t("Local paths")}>
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
            <dt className="text-soft">{t("Working folder")}</dt>
            <dd className="break-all font-mono text-xs">{c.workdir}</dd>
            <dt className="text-soft">{t("Data folder")}</dt>
            <dd className="break-all font-mono text-xs">{c.data_path}</dd>
          </dl>
        </Card>
      )}
    </div>
  );
}

export function DataSection() {
  const { t } = useI18n();
  const [info, setInfo] = useState<DataInfo | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [word, setWord] = useState("");
  const confirmWord = t("clear");
  const load = useCallback(async () => {
    try {
      setInfo(await getDataInfo());
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : String(e) });
    }
  }, []);
  useEffect(() => {
    const timer = setTimeout(load, 0);
    return () => clearTimeout(timer);
  }, [load]);

  return (
    <div className="space-y-4">
      <Card title={t("Data")} hint={t("All conversations, notes and published pages are kept only on this computer. Nothing is uploaded anywhere.")}>
        {info && (
          <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm sm:grid-cols-4">
            <div>
              <dt className="text-xs text-soft">{t("Conversations")}</dt>
              <dd>{info.conversations}</dd>
            </div>
            <div>
              <dt className="text-xs text-soft">{t("Tasks")}</dt>
              <dd>{info.tasks}</dd>
            </div>
            <div>
              <dt className="text-xs text-soft">{t("Published pages")}</dt>
              <dd>{info.published}</dd>
            </div>
            <div>
              <dt className="text-xs text-soft">{t("Database size")}</dt>
              <dd>{formatSize(info.db_bytes)}</dd>
            </div>
            <div>
              <dt className="text-xs text-soft">{t("Drive files")}</dt>
              <dd>{formatSize(info.uploads_bytes)}</dd>
            </div>
            <div>
              <dt className="text-xs text-soft">{t("Published pages size")}</dt>
              <dd>{formatSize(info.published_bytes)}</dd>
            </div>
          </dl>
        )}
        <div>
          <button
            type="button"
            onClick={async () => {
              try {
                await downloadExport();
                setMsg({ ok: true, text: t("Exported all conversations (JSON).") });
              } catch (e) {
                setMsg({ ok: false, text: e instanceof Error ? e.message : String(e) });
              }
            }}
            className="rounded-lg border border-line px-4 py-1.5 text-sm hover:border-accent"
          >
            {t("Export all conversations (JSON)")}
          </button>
        </div>
        {msg && (
          <p role="status" className={`text-sm ${msg.ok ? "text-accent" : "text-warn"}`}>
            {msg.text}
          </p>
        )}
      </Card>

      <Card
        title={t("Clear conversations")}
        hint={t("Deletes all conversations and task records. This cannot be undone. Drive files, published pages and settings are not affected. Export first.")}
      >
        <div className="flex flex-wrap items-center gap-2">
          <input
            className={`${inputCls} max-w-[12rem]`}
            value={word}
            onChange={(e) => setWord(e.target.value)}
            placeholder={t("Type “{word}” to confirm", { word: confirmWord })}
            aria-label={t("Type “{word}” to confirm", { word: confirmWord })}
          />
          <button
            type="button"
            disabled={word !== confirmWord}
            onClick={async () => {
              try {
                const r = await clearAllData();
                setWord("");
                setMsg({ ok: true, text: t("Deleted {count} conversations.", { count: r.deleted }) });
                load();
              } catch (e) {
                setMsg({ ok: false, text: e instanceof Error ? e.message : String(e) });
              }
            }}
            className="rounded-lg border border-warn/60 px-4 py-1.5 text-sm text-warn disabled:opacity-40"
          >
            {t("Clear all conversations")}
          </button>
        </div>
      </Card>
    </div>
  );
}
