"use client";

import { useCallback, useEffect, useState } from "react";
import { ChatGPTLogin } from "@/components/chatgpt-login";
import { COST_LABEL, confirmPaid } from "@/lib/cost";
import {
  addModel,
  addProvider,
  deleteModel,
  deleteProvider,
  getHealth,
  getModels,
  listProviders,
  providerModels,
  restoreModels,
  setActive,
  setModelEffort,
  setModelHidden,
  testModel,
  testProvider,
  updateProvider,
  type Health,
  type ModelEntry,
  type ModelsView,
  type Provider,
  type ProviderModels,
  type ProviderPreset,
} from "@/lib/api";
import { useI18n, type Translate } from "@/lib/i18n";
import { Card, Field, inputCls } from "@/components/settings/ui";

const EFFORT_LABEL: Record<string, string> = { minimal: "Minimal", low: "Low", medium: "Medium", high: "High", xhigh: "Extra high", max: "Maximum" };
type Note = { ok: boolean; text: string };

function money(perMillion: number | null, t: Translate): string {
  if (perMillion === null) return "—";
  return perMillion === 0 ? t("Free") : `$${perMillion < 1 ? perMillion.toFixed(2) : perMillion.toFixed(1)}`;
}
function ctx(n: number | null): string {
  if (!n) return "—";
  return n >= 1_000_000 ? `${(n / 1_000_000).toFixed(n % 1_000_000 ? 1 : 0)}M` : `${Math.round(n / 1000)}K`;
}
function host(url: string): string {
  try {
    return new URL(url).host;
  } catch {
    return url;
  }
}

function EffortPicker({ options, value, disabled, onPick, label }: { options: string[]; value: string | null; disabled?: boolean; onPick: (e: string) => void; label: string }) {
  const { t } = useI18n();
  return (
    <div className="flex flex-wrap items-center gap-1.5" role="radiogroup" aria-label={label}>
      {options.map((e) => (
        <button
          key={e}
          type="button"
          role="radio"
          aria-checked={value === e}
          disabled={disabled}
          onClick={() => onPick(e)}
          className={`rounded-lg border px-3 py-1 text-sm disabled:opacity-50 ${value === e ? "border-accent bg-accent-soft" : "border-line hover:border-accent"}`}
        >
          {t(EFFORT_LABEL[e] ?? e)}
        </button>
      ))}
    </div>
  );
}

/** Where models come from: OpenRouter from .env, plus any OpenAI-compatible service you add here. */
function ProvidersCard({ providers, presets, onChanged, onNote }: { providers: Provider[]; presets: ProviderPreset[]; onChanged: () => void; onNote: (n: Note) => void }) {
  const { t } = useI18n();
  const [results, setResults] = useState<Record<string, string>>({});
  const [editing, setEditing] = useState<string | null>(null);
  const [edit, setEdit] = useState({ name: "", base_url: "", api_key: "" });
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ name: "", base_url: "", api_key: "", preset: "" });
  const [busy, setBusy] = useState(false);

  const test = async (id: string) => {
    setResults((r) => ({ ...r, [id]: t("Testing…") }));
    try {
      const r = await testProvider(id);
      setResults((x) => ({ ...x, [id]: r.ok ? t("✓ Connected, {count} models ({seconds} s)", { count: r.count ?? 0, seconds: r.seconds ?? 0 }) : `✗ ${r.error}` }));
    } catch (e) {
      setResults((x) => ({ ...x, [id]: `✗ ${e instanceof Error ? e.message : String(e)}` }));
    }
  };

  const create = async () => {
    setBusy(true);
    try {
      const p = await addProvider(form);
      setForm({ name: "", base_url: "", api_key: "", preset: "" });
      setAdding(false);
      onChanged();
      onNote({ ok: true, text: t("Added provider “{name}”. Test the connection below, then pick models under “Add models”.", { name: p.name }) });
      test(p.id);
    } catch (e) {
      onNote({ ok: false, text: e instanceof Error ? e.message : String(e) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card
      title={t("Providers (where models come from)")}
      hint={t("Any OpenAI-compatible service can be connected: DeepSeek, Kimi, Zhipu, Qwen, SiliconFlow, local Ollama / LM Studio, or your own address. Keys are stored only on this computer and are sent only to their own provider.")}
    >
      <ul className="space-y-2">
        {providers.map((p) => (
          <li key={p.id} className="rounded-lg border border-line p-3">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2 text-sm font-medium">
                  {p.name}
                  <span className={`rounded px-1.5 text-xs font-normal ${p.ready ? "bg-accent-soft text-accent" : "bg-codebg text-warn"}`}>{p.ready ? (p.local ? t("Local") : t("Ready")) : t("No key")}</span>
                </div>
                <div className="break-all font-mono text-xs text-soft">{host(p.base_url)}</div>
              </div>
              <div className="flex shrink-0 flex-wrap gap-1.5">
                <button type="button" onClick={() => test(p.id)} disabled={!p.ready} className="rounded-md border border-line px-2.5 py-1 text-xs hover:border-accent disabled:opacity-40">
                  {t("Test connection")}
                </button>
                {!p.builtin && (
                  <>
                    <button
                      type="button"
                      onClick={() => {
                        setEditing(editing === p.id ? null : p.id);
                        setEdit({ name: p.name, base_url: p.base_url, api_key: "" });
                      }}
                      className="rounded-md border border-line px-2.5 py-1 text-xs hover:border-accent"
                    >
                      {t("Edit")}
                    </button>
                    <button
                      type="button"
                      onClick={async () => {
                        if (!window.confirm(t("Delete provider “{name}”? Its models will also be removed from the list (other providers are not affected).", { name: p.name }))) return;
                        try {
                          const r = await deleteProvider(p.id);
                          onChanged();
                          onNote({ ok: true, text: t("Deleted provider “{name}” and its {count} models.", { name: p.name, count: r.models_removed }) });
                        } catch (e) {
                          onNote({ ok: false, text: e instanceof Error ? e.message : String(e) });
                        }
                      }}
                      className="rounded-md border border-warn/60 px-2.5 py-1 text-xs text-warn"
                    >
                      {t("Delete")}
                    </button>
                  </>
                )}
              </div>
            </div>
            {p.builtin && (
              <p className="mt-1 text-xs text-soft">
                {t("This provider comes from the .env file (BIOMNI_CUSTOM_BASE_URL / BIOMNI_CUSTOM_API_KEY). To change it, edit that file directly.")}
              </p>
            )}
            {results[p.id] && <p className={`mt-1 text-xs ${results[p.id].startsWith("✓") ? "text-accent" : results[p.id].startsWith("✗") ? "text-warn" : "text-soft"}`}>{results[p.id]}</p>}
            {editing === p.id && (
              <div className="mt-3 grid gap-2 rounded-lg bg-codebg p-3 sm:grid-cols-2">
                <input className={inputCls} aria-label={t("Name")} value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} />
                <input className={inputCls} aria-label={t("Base URL")} value={edit.base_url} onChange={(e) => setEdit({ ...edit, base_url: e.target.value })} />
                <input
                  className={`${inputCls} sm:col-span-2`}
                  type="password"
                  autoComplete="off"
                  aria-label={t("New key")}
                  placeholder={p.has_key ? t("A key is saved. Enter a new one to replace it; leave blank to keep it.") : "API Key"}
                  value={edit.api_key}
                  onChange={(e) => setEdit({ ...edit, api_key: e.target.value })}
                />
                <div className="flex gap-2 sm:col-span-2">
                  <button
                    type="button"
                    onClick={async () => {
                      try {
                        await updateProvider(p.id, edit);
                        setEditing(null);
                        onChanged();
                        onNote({ ok: true, text: t("Saved.") });
                        test(p.id);
                      } catch (e) {
                        onNote({ ok: false, text: e instanceof Error ? e.message : String(e) });
                      }
                    }}
                    className="rounded-md bg-accent px-3 py-1 text-sm text-white dark:text-black"
                  >
                    {t("Save")}
                  </button>
                  <button type="button" onClick={() => setEditing(null)} className="rounded-md border border-line px-3 py-1 text-sm">
                    {t("Cancel")}
                  </button>
                </div>
              </div>
            )}
          </li>
        ))}
        {providers.length === 0 && <li className="text-sm text-soft">{t("No providers yet. Click “Add provider” below.")}</li>}
      </ul>

      {!adding ? (
        <button type="button" onClick={() => setAdding(true)} className="rounded-lg border border-line px-4 py-1.5 text-sm hover:border-accent">
          ＋ {t("Add provider")}
        </button>
      ) : (
        <div className="space-y-3 rounded-lg border border-accent/40 p-3">
          <div className="flex flex-wrap gap-1.5" aria-label={t("Common providers")}>
            {presets.map((pr) => (
              <button
                key={pr.id}
                type="button"
                title={pr.note}
                aria-pressed={form.preset === pr.id}
                onClick={() => setForm({ ...form, preset: pr.id, name: pr.id === "custom" ? form.name : pr.name, base_url: pr.base_url })}
                className={`rounded-full border px-2.5 py-0.5 text-xs ${form.preset === pr.id ? "border-accent bg-accent-soft text-accent" : "border-line text-soft hover:border-accent"}`}
              >
                {pr.name}
              </button>
            ))}
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            <input className={inputCls} aria-label={t("Provider name")} placeholder={t("Name, e.g. DeepSeek")} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <input
              className={inputCls}
              aria-label={t("Base URL")}
              placeholder={t("Base URL, e.g. {example}", { example: "https://api.deepseek.com/v1" })}
              value={form.base_url}
              onChange={(e) => setForm({ ...form, base_url: e.target.value })}
            />
            <input
              className={`${inputCls} sm:col-span-2`}
              type="password"
              autoComplete="off"
              aria-label="API Key"
              placeholder={t("API key (not needed for local Ollama / LM Studio)")}
              value={form.api_key}
              onChange={(e) => setForm({ ...form, api_key: e.target.value })}
            />
          </div>
          <p className="text-xs text-soft">
            {t("Clicking a name above only fills in the address, which may be out of date. After adding, click “Test connection” to check. Pay-per-use providers are treated as “Paid” models, and you confirm before using them.")}
          </p>
          <div className="flex gap-2">
            <button type="button" onClick={create} disabled={busy || !form.name.trim() || !form.base_url.trim()} className="rounded-lg bg-accent px-4 py-1.5 text-sm text-white disabled:opacity-40 dark:text-black">
              {busy ? t("Adding…") : t("Add")}
            </button>
            <button type="button" onClick={() => setAdding(false)} className="rounded-lg border border-line px-4 py-1.5 text-sm">
              {t("Cancel")}
            </button>
          </div>
        </div>
      )}
    </Card>
  );
}

export function ModelsSection() {
  const { t } = useI18n();
  const [mv, setMv] = useState<ModelsView | null>(null);
  const [presets, setPresets] = useState<ProviderPreset[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [msg, setMsg] = useState<Note | null>(null);
  const [tests, setTests] = useState<Record<string, Note | "running">>({});
  const [provider, setProvider] = useState("openrouter");
  const [q, setQ] = useState("");
  const [freeOnly, setFreeOnly] = useState(false);
  const [found, setFound] = useState<ProviderModels | null>(null);
  const [searching, setSearching] = useState(false);
  const [adding, setAdding] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [m, p] = await Promise.all([getModels(), listProviders()]);
      setMv(m);
      setPresets(p.presets);
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : String(e) });
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(load, 0);
    let alive = true;
    const poll = () =>
      getHealth()
        .then((h) => alive && setHealth(h))
        .catch(() => {});
    poll();
    const i = setInterval(poll, 3000);
    return () => {
      alive = false;
      clearTimeout(timer);
      clearInterval(i);
    };
  }, [load]);

  const ready = (mv?.providers ?? []).filter((p) => p.ready);
  const chosen = ready.find((p) => p.id === provider) ?? ready[0];

  // Search the chosen provider's real model list a moment after typing stops (and once at the start).
  useEffect(() => {
    if (!chosen) return;
    let alive = true;
    const timer = setTimeout(async () => {
      setSearching(true);
      try {
        const r = await providerModels(chosen.id, q, freeOnly);
        if (alive) setFound(r);
      } catch (e) {
        if (alive) setFound({ available: false, error: e instanceof Error ? e.message : String(e), results: [], have: [] });
      } finally {
        if (alive) setSearching(false);
      }
    }, q ? 350 : 0);
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [chosen, q, freeOnly]);

  const busy = !!health?.busy;
  const run = async (fn: () => Promise<ModelsView>, ok: string) => {
    setMsg(null);
    try {
      setMv(await fn());
      setMsg({ ok: true, text: ok });
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : String(e) });
    }
  };

  const test = async (m: ModelEntry) => {
    if (!confirmPaid(m, "test")) return;
    setTests((prev) => ({ ...prev, [m.id]: "running" }));
    try {
      const r = await testModel(m.id, m.cost === "paid");
      setTests((prev) => ({ ...prev, [m.id]: r.ok ? { ok: true, text: t("Working, took {seconds} s", { seconds: r.seconds }) } : { ok: false, text: r.error ?? t("Failed") } }));
    } catch (e) {
      setTests((prev) => ({ ...prev, [m.id]: { ok: false, text: e instanceof Error ? e.message : String(e) } }));
    }
  };

  const add = async (id: string) => {
    if (!chosen) return;
    setAdding(id);
    setMsg(null);
    try {
      const r = await addModel({ model: id, provider: chosen.id });
      setMv(r);
      setFound((f) => (f ? { ...f, have: [...f.have, id] } : f));
      setMsg({ ok: true, text: t("Added “{label}” ({cost}). Click “Test” first to confirm it works, then “Use”.", { label: r.added.label, cost: t(COST_LABEL[r.added.cost]) }) });
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : String(e) });
    } finally {
      setAdding(null);
    }
  };

  if (!mv) return <p className={`text-sm ${msg ? "text-warn" : "text-soft"}`}>{msg ? msg.text : t("Loading…")}</p>;

  const luna = mv.models.find((m) => m.source === "Codex");
  const others = mv.models.filter((m) => m.source !== "Codex");
  const onLuna = mv.active.source === "Codex";

  return (
    <div className="space-y-4">
      {msg && (
        <p role="status" className={`rounded-lg border p-2.5 text-sm ${msg.ok ? "border-accent/50 text-accent" : "border-warn/50 text-warn"}`}>
          {msg.text}
        </p>
      )}
      {busy && <p className="text-xs text-warn">{t("A task is running. You can switch models or change reasoning effort when it finishes.")}</p>}

      <Card title="ChatGPT" hint={t("Uses your ChatGPT subscription, with no extra charge. Only gpt-6-luna is allowed from the GPT family.")}>
        <ChatGPTLogin />
        {luna && (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-line p-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2 text-sm font-medium">
                {onLuna && <span className="text-accent">✓</span>}
                {luna.label}
                <span className="rounded bg-codebg px-1.5 text-xs font-normal text-soft">{t(COST_LABEL[luna.cost])}</span>
              </div>
              <div className="font-mono text-xs text-soft">{luna.model}</div>
            </div>
            {!onLuna && (
              <button
                type="button"
                disabled={busy}
                onClick={() => run(() => setActive({ id: luna.id }), t("Switched to “{label}”", { label: luna.label }))}
                className="rounded-md bg-accent px-3 py-1.5 text-sm text-white disabled:opacity-40 dark:text-black"
              >
                {t("Use")}
              </button>
            )}
          </div>
        )}
        <Field
          label={t("Reasoning effort")}
          hint={t("This really changes how the model works: higher effort means it thinks longer, is usually more accurate, and is slower. Under each answer, the effort actually used and the number of reasoning tokens are shown.")}
        >
          <EffortPicker
            label={t("ChatGPT reasoning effort")}
            options={luna?.effort_options ?? mv.efforts}
            value={luna?.effort ?? null}
            disabled={busy}
            onPick={(e) =>
              luna &&
              run(
                () => setModelEffort(luna.id, e),
                t("Reasoning effort set to “{effort}”{suffix}", {
                  effort: t(EFFORT_LABEL[e] ?? e),
                  suffix: onLuna ? t("; the next model call uses it") : t(" (takes effect after switching to ChatGPT)"),
                }),
              )
            }
          />
        </Field>
      </Card>

      <ProvidersCard providers={mv.providers} presets={presets} onChanged={load} onNote={setMsg} />

      <Card title={t("Other models")} hint={t("From the providers above. Paid models, or models with unclear billing, always ask you to confirm before use or testing.")}>
        <ul className="space-y-2">
          {others.map((m) => {
            const active = m.id === mv.active.id;
            const testState = tests[m.id];
            const noKey = !m.provider_ready;
            const gone = m.available === false;
            return (
              <li key={m.id} className={`rounded-lg border p-3 ${active ? "border-accent bg-accent-soft" : gone || noKey ? "border-warn/60" : "border-line"}`}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2 text-sm font-medium">
                      {active && <span className="text-accent">✓</span>}
                      <span className="truncate">{m.label}</span>
                      <span className={`rounded bg-codebg px-1.5 text-xs font-normal ${m.cost === "paid" ? "text-warn" : "text-soft"}`}>{t(COST_LABEL[m.cost])}</span>
                      <span className="rounded bg-codebg px-1.5 text-xs font-normal text-soft">{m.provider_name}</span>
                      {gone && <span className="rounded bg-codebg px-1.5 text-xs font-normal text-warn">{t("No longer on OpenRouter")}</span>}
                      {noKey && <span className="rounded bg-codebg px-1.5 text-xs font-normal text-warn">{t("Provider has no key")}</span>}
                    </div>
                    <div className="break-all font-mono text-xs text-soft">{m.model}</div>
                    {m.price && (
                      <div className="text-xs text-soft">
                        {t("Per million tokens: input {input} · output {output} · context {context}", {
                          input: money(m.price.prompt, t),
                          output: money(m.price.completion, t),
                          context: ctx(m.price.context),
                        })}
                      </div>
                    )}
                  </div>
                  <div className="flex shrink-0 flex-wrap items-center gap-1.5">
                    <label
                      className="mr-1 flex cursor-pointer items-center gap-1.5 text-xs text-soft"
                      title={t("Turn off to hide it from the model menu next to the input box (it still works here).")}
                    >
                      <input
                        type="checkbox"
                        checked={!m.hidden}
                        disabled={active}
                        onChange={(e) => run(() => setModelHidden(m.id, !e.target.checked), e.target.checked ? t("Now shown in the model menu") : t("Hidden from the model menu"))}
                      />
                      {t("Show in menu")}
                    </label>
                    <button type="button" onClick={() => test(m)} disabled={testState === "running" || noKey} className="rounded-md border border-line px-2.5 py-1 text-xs hover:border-accent disabled:opacity-50">
                      {testState === "running" ? t("Testing…") : t("Test")}
                    </button>
                    {!active && (
                      <button
                        type="button"
                        disabled={busy || noKey || gone}
                        onClick={() => confirmPaid(m) && run(() => setActive({ id: m.id, confirm_paid: m.cost === "paid" }), t("Switched to “{label}”", { label: m.label }))}
                        className="rounded-md bg-accent px-2.5 py-1 text-xs text-white disabled:opacity-40 dark:text-black"
                      >
                        {t("Use")}
                      </button>
                    )}
                    <button
                      type="button"
                      disabled={active}
                      title={active ? t("In use. Switch to another model first.") : t("Remove from list")}
                      onClick={() =>
                        window.confirm(
                          t("Delete “{label}”?{note}", {
                            label: m.label,
                            note: m.builtin ? ` ${t("(This is a built-in model. You can restore it later with “Restore deleted models”.)")}` : "",
                          }),
                        ) && run(() => deleteModel(m.id), t("Deleted"))
                      }
                      className="rounded-md border border-warn/60 px-2.5 py-1 text-xs text-warn disabled:opacity-40"
                    >
                      {t("Delete")}
                    </button>
                  </div>
                </div>
                {m.effort_options.length > 0 ? (
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <span className="text-xs text-soft">{t("Reasoning effort")}</span>
                    <EffortPicker
                      label={t("{label} reasoning effort", { label: m.label })}
                      options={m.effort_options}
                      value={m.effort}
                      disabled={busy}
                      onPick={(e) =>
                        run(
                          () => setModelEffort(m.id, e),
                          t("Reasoning effort for “{label}” set to “{effort}”{suffix}", {
                            label: m.label,
                            effort: t(EFFORT_LABEL[e] ?? e),
                            suffix: active ? t("; the next model call uses it") : t(" (takes effect when you use it)"),
                          }),
                        )
                      }
                    />
                  </div>
                ) : (
                  <p className="mt-1 text-xs text-soft">
                    {t("This model's reasoning effort cannot be adjusted (currently only ChatGPT and some models on OpenRouter support it).")}
                  </p>
                )}
                {testState && testState !== "running" && <p className={`mt-1 text-xs ${testState.ok ? "text-accent" : "text-warn"}`}>{testState.text}</p>}
              </li>
            );
          })}
          {others.length === 0 && (
            <li className="text-sm text-soft">{t("No other models right now. Pick a provider below to search and add one, or restore a deleted built-in model.")}</li>
          )}
        </ul>
        {mv.removed > 0 && (
          <button type="button" onClick={() => run(() => restoreModels(), t("Built-in models restored"))} className="rounded-lg border border-line px-3 py-1.5 text-sm hover:border-accent">
            {t("Restore deleted models ({count})", { count: mv.removed })}
          </button>
        )}
      </Card>

      <Card
        title={t("Add models")}
        hint={t("Pick a provider, then search its real model list. You can only add models that appear in the search, so names can't be mistyped. GPT models are not offered here.")}
      >
        {ready.length === 0 ? (
          <p className="rounded-lg border border-warn/50 p-2.5 text-sm text-warn">
            {t("No usable providers yet. First add one under “Providers” above (and enter its key).")}
          </p>
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <select
                value={chosen?.id ?? ""}
                onChange={(e) => (setProvider(e.target.value), setQ(""), setFound(null))}
                aria-label={t("Choose provider")}
                className="rounded-lg border border-line bg-paper px-3 py-1.5 text-sm outline-none focus:border-accent"
              >
                {ready.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
              <input
                className={`${inputCls} max-w-xs flex-1`}
                placeholder={t("Search, e.g. {examples}…", { examples: "kimi, deepseek, glm, qwen, llama" })}
                aria-label={t("Search models")}
                value={q}
                onChange={(e) => setQ(e.target.value)}
              />
              {found?.rich && (
                <label className="flex cursor-pointer items-center gap-1.5 text-sm text-soft">
                  <input type="checkbox" checked={freeOnly} onChange={(e) => setFreeOnly(e.target.checked)} />
                  {t("Free only")}
                </label>
              )}
              {searching && <span className="text-xs text-soft">{t("Searching…")}</span>}
            </div>
            {found && !found.available && <p className="rounded-lg border border-warn/50 p-2.5 text-sm text-warn">{found.error ?? t("Could not fetch this provider's model list.")}</p>}
            {found?.available && (
              <>
                {!found.rich && (
                  <p className="text-xs text-soft">
                    {t("This provider does not publish prices, so its models are treated as “Paid” (except local ones); you confirm before using them.")}
                    {found.total && found.total > found.results.length
                      ? ` ${t("{total} in total; showing the first {shown}. Type a keyword to narrow the list.", { total: found.total, shown: found.results.length })}`
                      : ""}
                  </p>
                )}
                <ul className="max-h-96 space-y-1.5 overflow-y-auto" aria-label={t("Search results")}>
                  {found.results.map((r) => {
                    const have = found.have.includes(r.id);
                    return (
                      <li key={r.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-line p-2.5">
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2 text-sm font-medium">
                            <span className="truncate">{found.rich ? r.name : r.id}</span>
                            {found.rich && (
                              <span className={`rounded bg-codebg px-1.5 text-xs font-normal ${r.free ? "text-soft" : "text-warn"}`}>{r.free ? t("Free") : t("Paid")}</span>
                            )}
                            {r.efforts.length > 0 && <span className="rounded bg-codebg px-1.5 text-xs font-normal text-soft">{t("Adjustable effort")}</span>}
                          </div>
                          {found.rich && (
                            <>
                              <div className="break-all font-mono text-xs text-soft">{r.id}</div>
                              <div className="text-xs text-soft">
                                {t("Per million tokens: input {input} · output {output} · context {context}", {
                                  input: money(r.prompt_per_m, t),
                                  output: money(r.completion_per_m, t),
                                  context: ctx(r.context),
                                })}
                              </div>
                            </>
                          )}
                        </div>
                        <button
                          type="button"
                          disabled={have || adding === r.id}
                          onClick={() => add(r.id)}
                          className="shrink-0 rounded-md bg-accent px-3 py-1 text-sm text-white disabled:opacity-40 dark:text-black"
                        >
                          {have ? t("Added") : adding === r.id ? t("Adding…") : t("Add")}
                        </button>
                      </li>
                    );
                  })}
                  {found.results.length === 0 && (
                    <li className="text-sm text-soft">
                      {t("Nothing found. Try another keyword{suffix}.", { suffix: found.rich ? t(", or untick “Free only”") : "" })}
                    </li>
                  )}
                </ul>
              </>
            )}
          </>
        )}
      </Card>
    </div>
  );
}
