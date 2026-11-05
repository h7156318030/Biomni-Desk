"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { COST_LABEL, confirmPaid } from "@/lib/cost";
import { getModels, getUsage, setActive, setModelEffort, type ModelEntry, type ModelsView, type Usage } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

const EFFORT_LABEL: Record<string, string> = { minimal: "Minimal", low: "Low", medium: "Medium", high: "High", xhigh: "Extra high", max: "Maximum" };

/** "gpt-6-luna" / "deepseek/deepseek-v3.2" -> something short enough for the button. */
function shortName(m: ModelEntry | undefined, fallback: string): string {
  if (!m) return fallback;
  if (m.source === "Codex") return "ChatGPT";
  return m.label.replace(/（.*?）/g, "");
}

/**
 * The model menu next to the send button: what is in use, how hard it thinks, and a one-click way to change either.
 * Models are grouped by where they come from; only models that can actually be used are enabled.
 */
export function ModelPicker({ busy, up = false }: { busy: boolean; up?: boolean }) {
  const { t } = useI18n();
  const [view, setView] = useState<ModelsView | null>(null);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);
  const box = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    try {
      setView(await getModels());
    } catch {}
  }, []);

  useEffect(() => {
    const timer = setTimeout(load, 0);
    return () => clearTimeout(timer);
  }, [load]);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const groups = useMemo(() => {
    if (!view) return [];
    const shown = view.models.filter((m) => !m.hidden || m.id === view.active.id);
    const order: string[] = [];
    for (const m of shown) if (!order.includes(m.provider_name)) order.push(m.provider_name);
    return order.map((name) => ({ name, items: shown.filter((m) => m.provider_name === name) }));
  }, [view]);

  if (!view) return null;
  const active = view.models.find((m) => m.id === view.active.id);
  const effort = view.active.reasoning_effort;
  const options = view.active.effort_options;
  const locked = busy || pending !== null;

  const act = async (key: string, fn: () => Promise<ModelsView>, close = false) => {
    setPending(key);
    setError(null);
    try {
      setView(await fn());
      if (close) setOpen(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setPending(null);
    }
  };

  const choose = (m: ModelEntry) => {
    if (m.id === view.active.id || !confirmPaid(m)) return;
    act(m.id, () => setActive({ id: m.id, confirm_paid: m.cost === "paid" }), true);
  };

  return (
    <div ref={box} className="relative">
      <button
        type="button"
        title={t("Choose model and reasoning effort")}
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => {
          load();
          setUsage(null);
          getUsage().then(setUsage).catch(() => {});
          setError(null);
          setOpen((o) => !o);
        }}
        className="flex items-center gap-2 rounded-full border border-line bg-card py-1.5 pl-3 pr-2.5 text-sm shadow-sm transition hover:border-accent"
      >
        <span className="h-2 w-2 shrink-0 rounded-full bg-accent" aria-hidden="true" />
        <span className="max-w-[9rem] truncate font-medium">{shortName(active, view.active.model)}</span>
        {options.length > 0 && <span className="rounded-full bg-accent-soft px-2 py-0.5 text-xs text-accent">{t(EFFORT_LABEL[effort] ?? effort)}</span>}
        <span className="text-xs text-soft" aria-hidden="true">
          ▾
        </span>
      </button>

      {open && (
        <div
          role="dialog"
          aria-label={t("Model and reasoning effort")}
          className={`absolute right-0 z-40 w-[22rem] max-w-[92vw] overflow-hidden rounded-2xl border border-line bg-panel shadow-2xl ${up ? "bottom-full mb-2" : "top-full mt-2"}`}
        >
          <div className="max-h-[70vh] overflow-y-auto">
            {busy && <p className="border-b border-line bg-codebg px-4 py-2 text-xs text-warn">{t("A task is running. You can switch when it finishes.")}</p>}

            <section className="border-b border-line px-4 py-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-medium tracking-wide text-soft">{t("Reasoning effort")}</h3>
                <span className="text-xs text-soft">{active?.label ?? ""}</span>
              </div>
              {options.length > 0 ? (
                <div className="mt-2 flex flex-wrap gap-1.5" role="radiogroup" aria-label={t("Reasoning effort")}>
                  {options.map((e) => (
                    <button
                      key={e}
                      type="button"
                      role="radio"
                      aria-checked={effort === e}
                      disabled={locked || !active}
                      onClick={() => active && act(`effort-${e}`, () => setModelEffort(active.id, e))}
                      className={`rounded-lg border px-3 py-1.5 text-sm transition disabled:opacity-50 ${effort === e ? "border-accent bg-accent-soft font-medium text-accent" : "border-line bg-card hover:border-accent"}`}
                    >
                      {t(EFFORT_LABEL[e] ?? e)}
                    </button>
                  ))}
                </div>
              ) : (
                <p className="mt-2 text-xs text-soft">
                  {t("This model's reasoning effort cannot be adjusted. Some models on ChatGPT and OpenRouter can.")}
                </p>
              )}
              {options.length > 0 && (
                <p className="mt-2 text-xs text-soft">
                  {t("Higher effort means the model thinks more, is usually more accurate, and is slower. The amount actually used is shown under each answer.")}
                </p>
              )}
            </section>

            <section className="px-2 py-2">
              {groups.map((g) => (
                <div key={g.name} className="mb-1">
                  <h3 className="px-2 pb-1 pt-2 text-[11px] font-medium tracking-wide text-soft">{g.name}</h3>
                  <ul>
                    {g.items.map((m) => {
                      const isActive = m.id === view.active.id;
                      const unusable = !m.provider_ready || m.available === false;
                      return (
                        <li key={m.id}>
                          <button
                            type="button"
                            role="menuitemradio"
                            aria-checked={isActive}
                            disabled={locked || unusable}
                            onClick={() => choose(m)}
                            className={`flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2 text-left transition disabled:opacity-50 ${isActive ? "bg-accent-soft" : "hover:bg-card"}`}
                          >
                            <span className={`grid h-4 w-4 shrink-0 place-items-center rounded-full border text-[10px] ${isActive ? "border-accent bg-accent text-white dark:text-black" : "border-line"}`} aria-hidden="true">
                              {isActive ? "✓" : ""}
                            </span>
                            <span className="min-w-0 flex-1">
                              <span className="block truncate text-sm font-medium">{m.label}</span>
                              <span className="block truncate text-xs text-soft">
                                {!m.provider_ready
                                  ? t("Provider has no key — add it in Settings first")
                                  : m.available === false
                                    ? t("No longer on OpenRouter")
                                    : m.price
                                      ? t("Input {input} · output {output} / million tokens", {
                                          input: m.price.prompt === 0 ? t("Free") : `$${m.price.prompt}`,
                                          output: m.price.completion === 0 ? t("Free") : `$${m.price.completion}`,
                                        })
                                      : m.note || m.model}
                              </span>
                            </span>
                            <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] ${m.cost === "paid" ? "bg-codebg text-warn" : "bg-codebg text-soft"}`}>
                              {t(COST_LABEL[m.cost])}
                            </span>
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              ))}
            </section>

            {error && <p className="border-t border-line px-4 py-2 text-xs text-warn">{error}</p>}

            <footer className="sticky bottom-0 flex items-center justify-between gap-3 border-t border-line bg-codebg px-4 py-2.5 text-xs text-soft">
              <span>
                {usage
                  ? t("{n} tasks today · {total} in all", {
                      n: usage.series[usage.series.length - 1]?.tasks ?? 0,
                      total: usage.tasks_total,
                    })
                  : " "}
              </span>
              <span className="flex gap-3">
                <Link href="/settings?section=usage" className="hover:text-accent">
                  {t("Usage")}
                </Link>
                <Link href="/settings?section=models" className="text-accent hover:underline">
                  {t("Manage models and providers →")}
                </Link>
              </span>
            </footer>
          </div>
        </div>
      )}
    </div>
  );
}
