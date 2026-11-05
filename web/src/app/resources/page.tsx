"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { getResources, type ResourceItem, type Resources } from "@/lib/api";
import { setPrefill } from "@/lib/prefill";
import { useI18n } from "@/lib/i18n";

type Tab = "tools" | "data" | "libraries";
const TABS: { id: Tab; label: string; hint: string }[] = [
  { id: "tools", label: "Tools", hint: "Functions the agent can call directly, grouped by name prefix" },
  { id: "data", label: "Datasets", hint: "Data files in the data lake, downloaded the first time they are used" },
  { id: "libraries", label: "Packages", hint: "Python / R / command-line software the agent can use when writing code" },
];

/** Tool status values as the backend reports them. */
const AVAILABLE = "available";

/** "query_uniprot" -> "query"; the verb in front groups tools without needing a hand-kept table. */
function groupOf(name: string): string {
  const head = name.split("_")[0];
  return head && head !== name ? head : "Other";
}

export default function ResourcesPage() {
  const router = useRouter();
  const { t } = useI18n();
  const [data, setData] = useState<Resources | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("tools");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");

  useEffect(() => {
    let alive = true;
    getResources()
      .then((r) => alive && setData(r))
      .catch((e) => alive && setError(e instanceof Error ? e.message : String(e)));
    return () => {
      alive = false;
    };
  }, []);

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    const items: ResourceItem[] = data ? data[tab] : [];
    return items.filter((i) => (!q || `${i.name} ${i.description}`.toLowerCase().includes(q)) && (tab !== "tools" || !status || i.status === status));
  }, [data, tab, query, status]);
  const groups = useMemo(() => {
    if (tab !== "tools") return [{ label: "", rows: shown }];
    const m = new Map<string, ResourceItem[]>();
    for (const i of shown) m.set(groupOf(i.name), [...(m.get(groupOf(i.name)) ?? []), i]);
    return [...m.entries()].sort((a, b) => b[1].length - a[1].length).map(([label, rows]) => ({ label, rows }));
  }, [shown, tab]);

  const use = (i: ResourceItem) => {
    const kind = tab === "tools" ? t("tool") : tab === "data" ? t("dataset") : t("package");
    setPrefill(t("Use the {kind} {name} to complete this:", { kind, name: i.name }));
    router.push("/");
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl px-6 py-8">
        <p className="text-[11px] tracking-wider text-soft">{t("Resources")}</p>
        <h1 className="font-serif text-3xl font-semibold">{t("Resources the agent can use")}</h1>
        <p className="mt-1 text-sm text-soft">
          {t("All the tools, datasets and packages this agent has loaded. Click one to go back to the workspace with it.")}
        </p>

        <div className="mt-5 flex flex-wrap items-center gap-2" role="tablist">
          {TABS.map((tb) => (
            <button
              key={tb.id}
              type="button"
              role="tab"
              aria-selected={tab === tb.id}
              onClick={() => setTab(tb.id)}
              className={`rounded-full border px-3 py-1 text-sm ${tab === tb.id ? "border-accent bg-accent-soft text-accent" : "border-line text-soft hover:border-accent"}`}
            >
              {t(tb.label)} <span className="text-xs">{data ? data[tb.id].length : "…"}</span>
            </button>
          ))}
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("Search by name or description…")}
            aria-label={t("Search resources")}
            className="ml-auto w-full rounded-lg border border-line bg-card px-3 py-1.5 text-sm outline-none focus:border-accent sm:w-64"
          />
        </div>
        <p className="mt-2 text-xs text-soft">{t(TABS.find((tb) => tb.id === tab)?.hint ?? "")}</p>
        {tab === "tools" && data?.tool_summary && (
          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
            <span className="text-soft">{t("Filter by tested status:")}</span>
            {[["", t("All {n}", { n: data.tools.length })], ...Object.entries(data.tool_summary).map(([k, n]) => [k, `${t(k)} ${n}`])].map(([k, label]) => (
              <button
                key={k}
                type="button"
                onClick={() => setStatus(k)}
                className={`rounded-full border px-2.5 py-0.5 ${status === k ? "border-accent bg-accent-soft text-accent" : "border-line text-soft hover:border-accent"}`}
              >
                {label}
              </button>
            ))}
            <span className="text-soft">
              {t(
                "“Restricted” tools mostly need command-line programs not installed on this machine (MACS2, HOMER, DiffDock, etc.); the interface notes missing for the query_* database tools have been filled in by us, and each was tested individually.",
              )}
            </span>
          </div>
        )}

        {error && <p className="mt-4 text-sm text-warn">{error}</p>}
        {data && !data.ready && <p className="mt-4 text-sm text-soft">{t("The agent is still loading; refresh this page shortly.")}</p>}

        {groups.map((g) => (
          <section key={g.label || "all"} className="mt-6">
            {g.label && (
              <h2 className="mb-2 font-mono text-sm text-soft">
                {t(g.label)}_* <span className="text-xs">({g.rows.length})</span>
              </h2>
            )}
            <ul className="grid gap-2 sm:grid-cols-2">
              {g.rows.map((i) => (
                <li key={i.name}>
                  <button
                    type="button"
                    onClick={() => use(i)}
                    className="h-full w-full rounded-xl border border-line bg-card p-3 text-left hover:border-accent"
                  >
                    <span className="flex items-center gap-2">
                      <span className="break-all font-mono text-sm font-medium">{i.name}</span>
                      {tab === "tools" && i.status && i.status !== AVAILABLE && (
                        <span className="shrink-0 rounded bg-codebg px-1.5 py-0.5 text-[11px] text-warn" title={i.note}>
                          {t(i.status)}
                        </span>
                      )}
                    </span>
                    <span className="mt-1 line-clamp-3 block text-xs text-soft">{i.description || t("(no description)")}</span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ))}
        {data?.ready && shown.length === 0 && <p className="mt-10 text-center text-sm text-soft">{t("No matching items.")}</p>}
      </div>
    </div>
  );
}
