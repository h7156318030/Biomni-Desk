"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  getConnectors,
  hubInspect,
  hubInstall,
  hubRefresh,
  hubSearch,
  hubStatus,
  type Connector,
  type HubFinding,
  type HubItem,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";

const TABS = [
  { key: "skills", label: "Skills" },
  { key: "tools", label: "Tools (MCP, reference)" },
  { key: "databases", label: "Databases" },
  { key: "software", label: "Software and lists (reference)" },
] as const;
type Tab = (typeof TABS)[number]["key"];

type Check = { url: string; verdict: string; findings: HubFinding[]; text: string };

/** The community hub, in the way Hermes' hub works: search an index of skills, see where each comes from and how it is trusted, scan it,
 *  and add it. Tools, databases and software are curated and shown for reference: this app runs its own database connectors. */
export default function LibraryPage() {
  const { t } = useI18n();
  const [tab, setTab] = useState<Tab>("skills");
  const [q, setQ] = useState("");
  const [trust, setTrust] = useState("");
  const [items, setItems] = useState<HubItem[] | null>(null);
  const [meta, setMeta] = useState<{ built_on: string; indexed: number; skipped: number; checked_on: string } | null>(null);
  const [connectors, setConnectors] = useState<Connector[] | null>(null);
  const [refresh, setRefresh] = useState<string>("");
  const [err, setErr] = useState<string | null>(null);
  const [check, setCheck] = useState<Record<string, Check>>({});
  const [result, setResult] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    if (tab === "databases") {
      getConnectors()
        .then((r) => setConnectors(r.connectors))
        .catch(() => setConnectors([]));
      return;
    }
    let alive = true;
    const timer = setTimeout(() => {
      hubSearch(q, tab === "software" ? "lists" : tab === "tools" ? "tools" : "skills", tab === "skills" ? trust : "")
        .then((r) => {
          if (!alive) return;
          setItems(r.items);
          setMeta({ built_on: r.built_on, indexed: r.indexed, skipped: r.skipped, checked_on: r.checked_on });
          setErr(null);
        })
        .catch((e) => alive && setErr(e instanceof Error ? e.message : String(e)));
    }, q ? 250 : 0);
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [q, tab, trust, version]);

  // while the index is rebuilding, follow its progress
  useEffect(() => {
    if (refresh !== "running") return;
    const i = setInterval(() => {
      hubStatus()
        .then((s) => {
          if (s.state === "running") return;
          setRefresh(s.message);
          setVersion((v) => v + 1);
        })
        .catch(() => {});
    }, 3000);
    return () => clearInterval(i);
  }, [refresh]);

  const startRefresh = async () => {
    setRefresh("running");
    try {
      const r = await hubRefresh();
      if (!r.started) setRefresh(t("A refresh is already running."));
    } catch (e) {
      setRefresh(e instanceof Error ? e.message : String(e));
    }
  };

  const inspect = async (url: string) => {
    setBusy(url);
    try {
      const c = await hubInspect(url);
      setCheck((m) => ({ ...m, [url]: { url, verdict: c.verdict, findings: c.findings, text: c.text } }));
      setResult((m) => ({ ...m, [url]: "" }));
    } catch (e) {
      setResult((m) => ({ ...m, [url]: e instanceof Error ? e.message : String(e) }));
    } finally {
      setBusy(null);
    }
  };

  const add = async (item: HubItem, force: boolean) => {
    if (!item.url) return;
    setBusy(item.url);
    try {
      const r = await hubInstall(item.url, force);
      if (r.ok) {
        setResult((m) => ({ ...m, [item.url!]: t("Added to your skills: {name}", { name: r.body?.skill?.title ?? item.name }) }));
        setVersion((v) => v + 1);
      } else {
        const d = r.body?.detail ?? {};
        setResult((m) => ({ ...m, [item.url!]: d.reason ?? t("Could not add this skill.") }));
      }
    } catch (e) {
      setResult((m) => ({ ...m, [item.url!]: e instanceof Error ? e.message : String(e) }));
    } finally {
      setBusy(null);
    }
  };

  const verdictLabel = (v: string) => (v === "safe" ? t("Safe: no risky patterns found") : v === "caution" ? t("Caution: risky patterns found") : t("Dangerous: never installed"));

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-4xl px-6 py-8">
        <h1 className="font-serif text-3xl font-semibold">{t("Community hub")}</h1>
        <p className="mt-1 text-sm text-soft">
          {t("Search community skills, tools, databases and software. Each skill is scanned before it is added; nothing is installed without your choice.")}
        </p>
        <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-soft">
          {meta && (
            <span>
              {t("Index: {count} skills, built {date}", { count: meta.indexed, date: meta.built_on || "—" })}
              {meta.skipped > 0 ? ` · ${t("{n} could not be read", { n: meta.skipped })}` : ""}
            </span>
          )}
          <button type="button" onClick={startRefresh} disabled={refresh === "running"} className="rounded-md border border-line px-2.5 py-1 hover:border-accent disabled:opacity-50">
            {refresh === "running" ? t("Refreshing…") : t("Refresh the index")}
          </button>
          {refresh && refresh !== "running" && <span>{refresh}</span>}
          <Link href="/skills" className="text-accent hover:underline">
            {t("Back to my skills")}
          </Link>
        </div>

        <div role="tablist" aria-label={t("Kind")} className="mt-5 flex flex-wrap gap-1">
          {TABS.map((k) => (
            <button
              key={k.key}
              type="button"
              role="tab"
              aria-selected={tab === k.key}
              onClick={() => setTab(k.key)}
              className={`rounded-full border px-3 py-1 text-xs ${tab === k.key ? "border-accent bg-accent-soft text-accent" : "border-line text-soft hover:border-accent"}`}
            >
              {t(k.label)}
            </button>
          ))}
        </div>

        {tab !== "databases" && (
          <div className="mt-4 flex flex-wrap gap-2">
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder={t("Search, e.g. single-cell, UniProt, alignment")}
              aria-label={t("Search the hub")}
              className="min-w-0 flex-1 rounded-md border border-line bg-card px-3 py-2 text-sm outline-none focus:border-accent"
            />
            {tab === "skills" && (
              <select value={trust} onChange={(e) => setTrust(e.target.value)} aria-label={t("Trust")} className="rounded-md border border-line bg-card px-2 py-2 text-sm">
                <option value="">{t("Any source")}</option>
                <option value="trusted">{t("Trusted source")}</option>
                <option value="community">{t("Community source")}</option>
              </select>
            )}
          </div>
        )}

        {err && <p className="mt-4 text-sm text-warn">{err}</p>}

        {tab === "databases" && (
          <div className="mt-5 space-y-3">
            <p className="text-sm text-soft">
              {t("These are the databases this app already queries, with their on and off switches in Settings. A new database needs a connector written into the app; the hub does not add databases by itself.")}
            </p>
            {connectors === null ? (
              <p className="text-sm text-soft">{t("Loading…")}</p>
            ) : (
              <ul className="space-y-2">
                {connectors.map((c) => (
                  <li key={c.id} className="flex items-center justify-between rounded-lg border border-line bg-card px-4 py-2.5 text-sm">
                    <span>{t(c.title)}</span>
                    <span className={`rounded px-1.5 text-xs ${c.enabled ? "bg-accent-soft text-accent" : "bg-codebg text-soft"}`}>{c.enabled ? t("On") : t("Off")}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {tab !== "databases" && items === null && !err && <p className="mt-6 text-sm text-soft">{t("Loading…")}</p>}
        {tab !== "databases" && items?.length === 0 && <p className="mt-6 text-sm text-soft">{t("Nothing matches this search.")}</p>}

        <ul className="mt-5 space-y-3">
          {tab !== "databases" &&
            items?.map((it) => {
              const c = it.url ? check[it.url] : undefined;
              const msg = it.url ? result[it.url] : undefined;
              const blocked = c?.verdict === "dangerous";
              return (
                <li key={it.id} className="rounded-lg border border-line bg-card p-4">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                      <a href={it.url ?? `https://github.com/${it.repo}`} target="_blank" rel="noreferrer" className="font-medium text-accent hover:underline">
                        {it.name}
                      </a>
                      <div className="font-mono text-xs text-soft">{it.kind === "skills" ? `${it.source} · ${it.path}` : it.repo}</div>
                    </div>
                    <div className="flex flex-wrap gap-1.5 text-xs">
                      {it.kind === "skills" && (
                        <span className={`rounded px-1.5 py-0.5 ${it.trust === "trusted" ? "bg-accent-soft text-accent" : "bg-codebg text-soft"}`}>
                          {it.trust === "trusted" ? t("Trusted source") : t("Community source")}
                        </span>
                      )}
                      {it.kind !== "skills" && <span className="rounded bg-codebg px-1.5 py-0.5 text-soft">{t("Reference only")}</span>}
                      {it.license && <span className="rounded bg-codebg px-1.5 py-0.5 text-soft">{it.license}</span>}
                      {it.archived && <span className="rounded bg-codebg px-1.5 py-0.5 text-warn">{t("Archived")}</span>}
                      {it.installed && <span className="rounded bg-accent-soft px-1.5 py-0.5 text-accent">{t("Installed")}</span>}
                    </div>
                  </div>
                  {it.description && <p className="mt-2 text-sm">{it.description}</p>}
                  {it.note && <p className="mt-1 text-xs text-soft">{it.note}</p>}
                  {it.archived && <p className="mt-1 text-xs text-warn">⚠ {t("Archived by its author: it will not be updated")}</p>}
                  {it.license === "unclear" && <p className="mt-1 text-xs text-warn">⚠ {t("Licence unclear: read the repository's LICENSE file")}</p>}

                  {it.kind === "skills" && it.url && !it.installed && (
                    <div className="mt-3 space-y-2">
                      <div className="flex flex-wrap gap-2">
                        <button type="button" onClick={() => inspect(it.url!)} disabled={busy === it.url} className="rounded-md border border-line px-3 py-1.5 text-sm hover:border-accent disabled:opacity-50">
                          {busy === it.url ? t("Checking…") : t("Scan before adding")}
                        </button>
                        {c && !blocked && (
                          <button type="button" onClick={() => add(it, c.verdict === "caution")} disabled={busy === it.url} className="rounded-md bg-accent px-3 py-1.5 text-sm text-white disabled:opacity-40 dark:text-black">
                            {c.verdict === "caution" ? t("I have read the findings: add anyway") : t("Add to my skills")}
                          </button>
                        )}
                      </div>
                      {c && (
                        <div className={`rounded-md border p-2.5 text-sm ${blocked ? "border-warn/60" : "border-line"}`}>
                          <p className={blocked ? "text-warn" : c.verdict === "caution" ? "text-warn" : "text-accent"}>{verdictLabel(c.verdict)}</p>
                          {c.findings.length > 0 && (
                            <ul className="mt-1.5 space-y-1 font-mono text-xs">
                              {c.findings.slice(0, 12).map((f, i) => (
                                <li key={i}>
                                  {t("line {n}", { n: f.line })} · {f.severity} · {f.rule}: <span className="text-soft">{f.text}</span>
                                </li>
                              ))}
                            </ul>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                  {msg && <p className="mt-2 text-sm text-soft">{msg}</p>}
                </li>
              );
            })}
        </ul>
      </div>
    </div>
  );
}
