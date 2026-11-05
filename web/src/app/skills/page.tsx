"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { CopyButton } from "@/components/events";
import { setPrefill } from "@/lib/prefill";
import { tr, useI18n } from "@/lib/i18n";
import {
  createSkill,
  deleteSkill,
  getSkill,
  listSkills,
  toggleSkill,
  updateSkill,
  type Skill,
  type SkillInput,
} from "@/lib/api";

const EMPTY: SkillInput = { id: "", title: "", description: "", category: "", when_to_use: "", avoid: "", uses: "", chain: "", body: "" };
const SOURCES = [
  { key: "all", label: "All" },
  { key: "mine", label: "Mine" },
  { key: "builtin", label: "Built-in" },
] as const;

function Field({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <label className="block text-sm">
      <span className="font-medium">{label}</span>
      {hint && <span className="ml-2 text-xs text-soft">{hint}</span>}
      <div className="mt-1">{children}</div>
    </label>
  );
}

const inputCls = "w-full rounded-md border border-line bg-paper px-2.5 py-1.5 outline-none focus:border-accent";

/** The on/off pill on a skill card and in its header. */
function EnabledPill({ on, onClick, label }: { on: boolean; onClick: () => void; label: string }) {
  const { t } = useI18n();
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={label}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      className={`shrink-0 rounded-full border px-2.5 py-0.5 text-xs ${on ? "border-accent bg-accent-soft text-accent" : "border-line text-soft hover:border-accent"}`}
    >
      {on ? t("✓ Enabled") : t("Disabled")}
    </button>
  );
}

export default function SkillsPage() {
  const router = useRouter();
  const { t } = useI18n();
  const [items, setItems] = useState<Skill[]>([]);
  const [source, setSource] = useState<(typeof SOURCES)[number]["key"]>("all");
  const [category, setCategory] = useState("");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<Skill | null>(null);
  const [tab, setTab] = useState<"overview" | "file">("overview");
  const [editing, setEditing] = useState<SkillInput | null>(null);
  const [isNew, setIsNew] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setItems(await listSkills());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(refresh, 0);
    return () => clearTimeout(timer);
  }, [refresh]);

  const open = async (id: string) => {
    setError(null);
    setEditing(null);
    setTab("overview");
    try {
      setSelected(await getSkill(id));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const startNew = (from?: Skill) => {
    setSelected(null);
    setIsNew(true);
    setEditing(from ? { ...from, id: `${from.id}-copy`.slice(0, 48) } : { ...EMPTY });
    setError(null);
  };

  const save = async () => {
    if (!editing) return;
    setError(null);
    try {
      const saved = isNew ? await createSkill(editing) : await updateSkill(editing.id!, editing);
      setEditing(null);
      setSelected(saved);
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const toggle = async (s: Skill) => {
    await toggleSkill(s.id, !s.enabled);
    setSelected((cur) => (cur && cur.id === s.id ? { ...cur, enabled: !s.enabled } : cur));
    refresh();
  };

  const remove = async (s: Skill) => {
    if (!window.confirm(tr("Delete skill “{title}”?", { title: s.title }))) return;
    await deleteSkill(s.id);
    setSelected(null);
    refresh();
  };

  const counts = { all: items.length, mine: items.filter((s) => s.source === "mine").length, builtin: items.filter((s) => s.source === "builtin").length };
  const categories = useMemo(() => [...new Set(items.map((s) => s.category).filter(Boolean))].sort(), [items]);
  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return items.filter(
      (s) =>
        (source === "all" || s.source === source) &&
        (!category || s.category === category) &&
        (!q || `${s.title}${s.id}${s.description}${s.category}`.toLowerCase().includes(q)),
    );
  }, [items, source, category, query]);
  const groups = [
    { label: "My skills", items: shown.filter((s) => s.source === "mine") },
    { label: "Built-in skills", items: shown.filter((s) => s.source === "builtin") },
  ].filter((g) => g.items.length);
  const set = (k: keyof SkillInput) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setEditing((cur) => (cur ? { ...cur, [k]: e.target.value } : cur));

  const back = () => {
    setSelected(null);
    setEditing(null);
    setError(null);
  };
  const rawFile = (s: Skill) =>
    `---\ntitle: ${s.title}\ndescription: ${s.description}\ncategory: ${s.category ?? ""}\nwhen_to_use: ${s.when_to_use ?? ""}\navoid: ${s.avoid ?? ""}\nuses: ${s.uses ?? ""}\nchain: ${s.chain ?? ""}\n---\n${s.body}`;

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl px-6 py-8">
        {error && <p className="mb-3 rounded-lg border border-warn/50 bg-card p-3 text-sm text-warn">{error}</p>}

        {!selected && !editing && (
          <>
            <header className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <p className="text-[11px] tracking-wider text-soft">{t("Skill centre")}</p>
                <h1 className="font-serif text-3xl font-semibold">{t("Skills")}</h1>
                <p className="mt-1 text-sm text-soft">
                  {t("Skills are manuals written for the agent. Once enabled, the agent refers to them automatically in related tasks.")}
                </p>
              </div>
              <button type="button" onClick={() => startNew()} className="rounded-full bg-accent px-4 py-2 text-sm text-white dark:text-black">
                ＋ {t("New skill")}
              </button>
            </header>

            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t("Search all skills…")}
              aria-label={t("Search skills")}
              className="mt-5 w-full rounded-xl border border-line bg-card px-4 py-2.5 text-sm outline-none focus:border-accent"
            />
            <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
              <span className="text-xs text-soft">{t("Source")}</span>
              {SOURCES.map((src) => (
                <button
                  key={src.key}
                  type="button"
                  aria-pressed={source === src.key}
                  onClick={() => setSource(src.key)}
                  className={`rounded-full border px-3 py-1 ${source === src.key ? "border-accent bg-accent-soft text-accent" : "border-line text-soft hover:border-accent"}`}
                >
                  {t(src.label)} <span className="text-xs">{counts[src.key]}</span>
                </button>
              ))}
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                aria-label={t("Category")}
                className="ml-auto rounded-lg border border-line bg-card px-3 py-1.5 text-sm outline-none focus:border-accent"
              >
                <option value="">{t("All categories")}</option>
                {categories.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>

            {groups.map((g) => (
              <section key={g.label} className="mt-6">
                <h2 className="mb-2 text-sm font-medium text-soft">
                  {t(g.label)} <span className="text-xs">({g.items.length})</span>
                </h2>
                <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {g.items.map((s) => (
                    <li key={s.id}>
                      <div
                        role="button"
                        tabIndex={0}
                        onClick={() => open(s.id)}
                        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), open(s.id))}
                        className="flex h-full cursor-pointer flex-col rounded-xl border border-line bg-card p-4 transition hover:border-accent hover:shadow-sm"
                      >
                        <h3 className="font-serif text-base font-semibold">{s.title}</h3>
                        <p className="mt-0.5 text-[11px] tracking-wider text-soft">{s.category || t("Uncategorised")}</p>
                        <p className="mt-2 line-clamp-3 flex-1 text-sm text-soft">{s.description}</p>
                        <div className="mt-3 flex items-center justify-between gap-2">
                          <span className="text-xs text-soft">{s.source === "builtin" ? t("Built-in") : t("Mine")}</span>
                          <EnabledPill on={s.enabled} label={t("{title}: enable", { title: s.title })} onClick={() => toggle(s)} />
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
            {groups.length === 0 && (
              <p className="mt-10 text-center text-sm text-soft">
                {items.length ? t("No matching skills. Try another keyword or category.") : t("No skills yet.")}
              </p>
            )}
          </>
        )}

        {selected && !editing && (
          <article className="space-y-4">
            <button type="button" onClick={back} className="text-sm text-soft hover:text-ink">
              {t("← Back to skill centre")}
            </button>
            <header className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <h1 className="font-serif text-3xl font-semibold">{selected.title}</h1>
                <p className="mt-1 text-sm text-soft">{selected.description}</p>
                <p className="mt-2 flex flex-wrap items-center gap-2 text-xs text-soft">
                  {selected.category && <span className="rounded bg-codebg px-1.5 py-0.5">{selected.category}</span>}
                  <span>{selected.source === "builtin" ? t("Built-in skill (read-only)") : t("My skill")}</span>
                  <span className="font-mono">{selected.id}</span>
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <EnabledPill on={selected.enabled} label={t("Enable this skill")} onClick={() => toggle(selected)} />
                <button
                  type="button"
                  onClick={() => {
                    setPrefill(t("Use the skill “{title}” to complete this:", { title: selected.title }));
                    router.push("/");
                  }}
                  className="rounded-lg bg-accent px-3 py-1.5 text-sm text-white dark:text-black"
                >
                  {t("Start a task with it")}
                </button>
                {selected.source === "mine" ? (
                  <>
                    <button
                      type="button"
                      onClick={() => {
                        setIsNew(false);
                        setEditing({ ...selected });
                      }}
                      className="rounded-lg border border-line px-3 py-1.5 text-sm hover:border-accent"
                    >
                      {t("Edit")}
                    </button>
                    <button type="button" onClick={() => remove(selected)} className="rounded-lg border border-warn/60 px-3 py-1.5 text-sm text-warn">
                      {t("Delete")}
                    </button>
                  </>
                ) : (
                  <button type="button" onClick={() => startNew(selected)} className="rounded-lg border border-line px-3 py-1.5 text-sm hover:border-accent">
                    {t("Copy as my skill")}
                  </button>
                )}
              </div>
            </header>
            {selected.source === "builtin" && <p className="text-xs text-soft">{t("Copy this skill to get a version you can edit.")}</p>}

            <div className="flex gap-1 border-b border-line" role="tablist">
              {(
                [
                  ["overview", "Overview"],
                  ["file", "Source file"],
                ] as const
              ).map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  role="tab"
                  aria-selected={tab === id}
                  onClick={() => setTab(id)}
                  className={`-mb-px border-b-2 px-3 py-1.5 text-sm ${tab === id ? "border-accent text-ink" : "border-transparent text-soft hover:text-ink"}`}
                >
                  {t(label)}
                </button>
              ))}
            </div>

            {tab === "overview" ? (
              <>
                <dl className="grid gap-3 rounded-xl border border-line bg-card p-4 text-sm sm:grid-cols-2">
                  {[
                    ["When to use", selected.when_to_use],
                    ["Not for", selected.avoid],
                    ["Main dependencies", selected.uses],
                    ["Upstream / downstream", selected.chain],
                  ]
                    .filter(([, v]) => v)
                    .map(([k, v]) => (
                      <div key={k}>
                        <dt className="text-xs text-soft">{t(k)}</dt>
                        <dd>{v}</dd>
                      </div>
                    ))}
                </dl>
                <div className="md rounded-xl border border-line bg-card p-5">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{selected.body}</ReactMarkdown>
                </div>
              </>
            ) : (
              <div className="rounded-xl border border-line bg-card">
                <div className="flex items-center justify-between border-b border-line px-4 py-2 text-xs text-soft">
                  <span className="font-mono">{selected.id}.md</span>
                  <CopyButton text={rawFile(selected)} />
                </div>
                <pre className="max-h-[32rem] overflow-auto p-4 font-mono text-[13px] leading-snug whitespace-pre-wrap">{rawFile(selected)}</pre>
              </div>
            )}
          </article>
        )}

        {editing && (
          <form
            className="mx-auto max-w-3xl space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              save();
            }}
          >
            <button type="button" onClick={back} className="text-sm text-soft hover:text-ink">
              {t("← Back to skill centre")}
            </button>
            <h2 className="font-serif text-2xl font-semibold">{isNew ? t("New skill") : t("Edit skill")}</h2>
            {isNew && (
              <Field label={t("Skill ID")} hint={t("Lowercase letters, digits, underscores and hyphens. Cannot be changed after creation.")}>
                <input className={inputCls} value={editing.id ?? ""} onChange={set("id")} placeholder={t("e.g. {example}", { example: "my-rnaseq-qc" })} />
              </Field>
            )}
            <Field label={t("Title")}>
              <input className={inputCls} value={editing.title ?? ""} onChange={set("title")} />
            </Field>
            <Field label={t("One-line summary")}>
              <input className={inputCls} value={editing.description ?? ""} onChange={set("description")} />
            </Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={t("Category")}>
                <input className={inputCls} value={editing.category ?? ""} onChange={set("category")} />
              </Field>
              <Field label={t("Main dependencies")} hint={t("Tools or packages, comma-separated")}>
                <input className={inputCls} value={editing.uses ?? ""} onChange={set("uses")} />
              </Field>
            </div>
            <Field label={t("When to use")}>
              <input className={inputCls} value={editing.when_to_use ?? ""} onChange={set("when_to_use")} />
            </Field>
            <Field label={t("Not for / use instead")}>
              <input className={inputCls} value={editing.avoid ?? ""} onChange={set("avoid")} />
            </Field>
            <Field label={t("Upstream / downstream")} hint={t("Upstream skills or outputs it depends on")}>
              <input className={inputCls} value={editing.chain ?? ""} onChange={set("chain")} />
            </Field>
            <Field label={t("Body (Markdown)")} hint={t("Steps, input and output conventions, cautions")}>
              <textarea className={`${inputCls} min-h-[18rem] font-mono text-[13px]`} value={editing.body ?? ""} onChange={set("body")} />
            </Field>
            <div className="flex gap-2">
              <button type="submit" className="rounded-lg bg-accent px-4 py-2 text-sm text-white dark:text-black">
                {t("Save")}
              </button>
              <button type="button" onClick={() => setEditing(null)} className="rounded-lg border border-line px-4 py-2 text-sm">
                {t("Cancel")}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
