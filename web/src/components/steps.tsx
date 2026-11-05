"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useMemo, useState } from "react";
import { CodeBlock } from "@/components/code";
import { ArtifactLink, CopyButton, EventView, looksFailed, preview } from "@/components/events";
import type { AgentEvent } from "@/lib/api";
import { tr, useI18n } from "@/lib/i18n";

/** What a piece of code is doing, in words a reader can follow (the official app shows "Searching literature…" cards). */
const KINDS: { re: RegExp; label: string; badge: string }[] = [
  { re: /\b(author_papers|openalex_author_candidates)\b/, label: "Search author papers", badge: "Literature" },
  { re: /\b(pubmed_search|paper_abstracts|query_pubmed)\b/, label: "Search PubMed", badge: "Literature" },
  { re: /\beuropepmc_search\b/, label: "Search Europe PMC (incl. preprints)", badge: "Literature" },
  { re: /\b(query_arxiv|query_scholar)\b/, label: "Search literature", badge: "Literature" },
  { re: /\bweb_search\b|\bsearch_google\b|\badvanced_web_search_claude\b/, label: "Web search", badge: "Web" },
  { re: /\b(read_webpage|extract_url_content|extract_pdf_content)\b/, label: "Read web page", badge: "Web" },
  { re: /matplotlib|seaborn|plotly|plt\./, label: "Plotting", badge: "Chart" },
  { re: /read_csv|read_excel|pandas|scanpy|anndata|numpy/, label: "Data analysis", badge: "Data" },
  { re: /\bbiomni\.tool\.|from biomni/, label: "Call a Biomni tool", badge: "Tool" },
];

const CALL = /\b(author_papers|openalex_author_candidates|pubmed_search|paper_abstracts|query_pubmed|europepmc_search|query_arxiv|query_scholar|web_search|search_google|advanced_web_search_claude|read_webpage|extract_url_content|extract_pdf_content)\(([^)]*)\)/;

/** The one-line title the model writes as the first comment of a code block ("# Query TP53 variants"). */
export function codeTitle(code: string): string {
  const first = code.trimStart().split(/\r?\n/, 1)[0] ?? "";
  const m = /^#\s*(.{2,60})$/.exec(first.trim());
  return m && !/^(-\*-|!|%)/.test(m[1]) ? m[1].trim() : "";
}

export function describeCode(code: string): { label: string; badge: string; inputs: [string, string][] } {
  const m = CALL.exec(code);
  // the function actually called decides the label; the imports alone (web_search AND read_webpage) are ambiguous
  const kind = (m && KINDS.find((k) => k.re.test(m[1]))) || KINDS.find((k) => k.re.test(code));
  const inputs: [string, string][] = [];
  if (m) {
    const args = m[2];
    const re = /(?:(\w+)\s*=\s*)?("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|[\w.\-]+)/g;
    let a: RegExpExecArray | null;
    let pos = 0;
    while ((a = re.exec(args)) && inputs.length < 5) {
      const val = a[2].replace(/^["']|["']$/g, "");
      inputs.push([a[1] ?? (pos++ === 0 ? tr("query") : tr("argument {n}", { n: pos })), val]);
    }
  }
  return { label: codeTitle(code) || (kind?.label ?? "Run code"), badge: kind?.badge ?? "Code", inputs };
}

export type SourceCard = { n: number; kind: "paper" | "web"; title: string; meta: string; by?: string; id?: string; doi?: string; url?: string; note?: string };

/** Pull numbered source cards out of a tool's printed output (the fixed layouts of lit.py and web.py). */
export function parseSources(text: string): SourceCard[] {
  const lines = text.split(/\r?\n/);
  const out: SourceCard[] = [];
  for (let i = 0; i < lines.length; i++) {
    const L = lines[i];
    let m: RegExpExecArray | null;
    if ((m = /^(?:PMID|MED|PPR|PMC): ?(\S+) \| (.+)$/.exec(L)) || (m = /^PMID: (\d+) \| (.+)$/.exec(L))) {
      const parts = m[2].split(" | ");
      const doi = parts.find((p) => p.startsWith("DOI: "))?.slice(5);
      const rest = parts.filter((p) => !p.startsWith("DOI: ") && !p.startsWith("["));
      const card: SourceCard = { n: out.length + 1, kind: "paper", title: rest[0] ?? "", by: rest[1], meta: rest[2] ?? "", id: m[1], doi };
      const next = (lines[i + 1] ?? "").trim();
      // Older outputs printed these labels in Chinese; both spellings are read.
      if (/^(Affiliation|Abstract|作者单位|摘要):/.test(next)) card.note = next;
      out.push(card);
    } else if ((m = /^\[(\d+)\] (.+?) \| (\S+)$/.exec(L)) && /^\s+https?:\/\//.test(lines[i + 1] ?? "")) {
      out.push({ n: out.length + 1, kind: "web", title: m[2], meta: m[3], url: lines[i + 1].trim(), note: (lines[i + 2] ?? "").trim() });
    }
  }
  return out;
}

function Sources({ cards }: { cards: SourceCard[] }) {
  const { t } = useI18n();
  const [all, setAll] = useState(false);
  const shown = all ? cards : cards.slice(0, 8);
  return (
    <div className="space-y-2">
      <p className="text-xs text-soft">{t("{n} sources recorded, which can be cited in the answer", { n: cards.length })}</p>
      <ol className="space-y-2">
        {shown.map((c) => {
          const href = c.kind === "web" ? c.url : c.doi ? `https://doi.org/${c.doi}` : c.id ? `https://pubmed.ncbi.nlm.nih.gov/${c.id}/` : undefined;
          return (
            <li key={c.n} className="rounded-lg border border-line bg-card p-2.5 text-sm">
              <div className="flex items-center gap-2 text-xs text-soft">
                <span className="font-mono">[{c.n}]</span>
                <span className="rounded bg-codebg px-1.5 py-0.5">{c.kind === "web" ? t("Web") : t("Literature")}</span>
                <span className="truncate">{c.meta}</span>
              </div>
              <a href={href} target="_blank" rel="noreferrer" className="mt-1 block font-medium leading-snug text-accent hover:underline">
                {c.title}
              </a>
              {c.by && <div className="mt-0.5 text-xs text-soft">{c.by}</div>}
              {c.note && <div className="mt-1 line-clamp-3 text-xs text-soft">{c.note}</div>}
              {c.kind === "paper" && c.id && <div className="mt-1 font-mono text-xs text-soft">PMID: {c.id}{c.doi ? ` · DOI: ${c.doi}` : ""}</div>}
            </li>
          );
        })}
      </ol>
      {cards.length > 8 && (
        <button type="button" onClick={() => setAll(!all)} className="text-xs text-accent hover:underline">
          {all ? t("Collapse") : t("Show all {n}", { n: cards.length })}
        </button>
      )}
    </div>
  );
}

type Step = { key: number; narration?: string; code?: Extract<AgentEvent, { type: "code" }>; obs?: Extract<AgentEvent, { type: "observation" }> };

function StepCard({ step, turnId, running }: { step: Step; turnId: string; running: boolean }) {
  const { t, lang } = useI18n();
  const code = step.code;
  // describeCode builds labels in the current language, so the memo is also keyed on it
  const d = useMemo(() => describeCode(code?.code ?? ""), [code?.code, lang]);
  const cards = useMemo(() => (step.obs ? parseSources(step.obs.text) : []), [step.obs]);
  const failed = step.obs ? looksFailed(step.obs.text) : false;
  const secs = (step.obs?.elapsed ?? code?.elapsed) as number | undefined;
  const arts = step.obs?.artifacts ?? [];
  const long = (step.obs?.text.length ?? 0) > 4000;
  return (
    <div id={`ev-${turnId}-${step.obs?.seq ?? code?.seq ?? step.key}`} className="space-y-1.5">
      {step.narration && <p className="px-0.5 text-sm text-ink">{preview(step.narration, 240)}</p>}
      <details className={`group rounded-lg border bg-card ${failed ? "border-warn" : "border-line"}`}>
        <summary className="flex cursor-pointer select-none items-center gap-2 px-3 py-2 text-sm marker:content-none">
          <span className="inline-block text-xs text-soft transition-transform group-open:rotate-90">▸</span>
          <span className="rounded bg-accent-soft px-1.5 py-0.5 text-xs text-accent">{t(d.badge)}</span>
          <span className="font-medium">{t(d.label)}</span>
          <span className="min-w-0 flex-1 truncate text-soft">{d.inputs[0] ? `${d.inputs[0][1]}` : codeTitle(code?.code ?? "") ? "" : preview(code?.code ?? "", 50)}</span>
          {running && !step.obs ? (
            <span className="pulse text-xs text-accent">{t("Running…")}</span>
          ) : (
            <span className="shrink-0 text-xs text-soft">
              {failed ? <span className="text-warn">{t("Error")} </span> : <span className="text-accent">✓ </span>}
              {secs !== undefined && `${secs.toFixed(1)}s`}
            </span>
          )}
        </summary>
        <div className="space-y-3 border-t border-line px-3 py-3">
          <section>
            <h4 className="mb-1 text-xs font-medium text-soft">{t("Input")}</h4>
            {d.inputs.length > 0 && (
              <dl className="mb-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 rounded-md bg-codebg p-2 text-sm">
                {d.inputs.map(([k, v], i) => (
                  <div key={i} className="contents">
                    <dt className="text-xs text-soft">{k}</dt>
                    <dd className="break-words">{v}</dd>
                  </div>
                ))}
              </dl>
            )}
            {code && (
              <details className="rounded-md border border-line">
                <summary className="cursor-pointer px-2 py-1 text-xs text-soft">{t("Code ({language})", { language: code.language })}</summary>
                <div className="px-2 pb-2">
                  <div className="mb-1 flex justify-end">
                    <CopyButton text={code.code} />
                  </div>
                  <CodeBlock code={code.code} />
                </div>
              </details>
            )}
          </section>
          {step.obs && (
            <section>
              <h4 className="mb-1 text-xs font-medium text-soft">{t("Output")}</h4>
              {cards.length > 0 && <Sources cards={cards} />}
              <details open={cards.length === 0} className={cards.length ? "mt-2 rounded-md border border-line" : ""}>
                {cards.length > 0 && <summary className="cursor-pointer px-2 py-1 text-xs text-soft">{t("Raw output")}</summary>}
                <pre className="max-h-80 overflow-auto rounded-md bg-codebg p-3 font-mono text-[13px] leading-snug whitespace-pre-wrap">
                  {long ? `${step.obs.text.slice(0, 4000)}\n${t("…(truncated, {n} characters in all)", { n: step.obs.text.length })}` : step.obs.text}
                </pre>
              </details>
              {arts.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-2">
                  {arts.map((a) => (
                    <ArtifactLink key={a.path} a={a} />
                  ))}
                </div>
              )}
            </section>
          )}
        </div>
      </details>
    </div>
  );
}

/** The working trace as short narrations plus one card per tool call, instead of a stack of code and output blocks. */
export function StepCards({ items, turnId, live }: { items: AgentEvent[]; turnId: string; live: boolean }) {
  const nodes: React.ReactNode[] = [];
  let narration: string | undefined;
  let current: Step | null = null;
  const flush = (last: boolean) => {
    if (current) {
      nodes.push(<StepCard key={`s${current.key}`} step={current} turnId={turnId} running={live && last} />);
      current = null;
    }
  };
  items.forEach((ev, idx) => {
    if (ev.type === "reasoning") {
      flush(false);
      narration = ev.text;
    } else if (ev.type === "code") {
      flush(false);
      current = { key: ev.seq, narration, code: ev };
      narration = undefined;
    } else if (ev.type === "observation") {
      if (current && !(current as Step).obs) (current as Step).obs = ev;
      else {
        flush(false);
        current = { key: ev.seq, obs: ev };
      }
      flush(idx === items.length - 1);
    } else {
      flush(false);
      nodes.push(
        <div key={`e${ev.seq}`} id={`ev-${turnId}-${ev.seq}`}>
          <EventView ev={ev} turnId={turnId} />
        </div>,
      );
    }
  });
  flush(true);
  if (narration) nodes.push(<p key="tail" className="px-0.5 text-sm">{preview(narration, 240)}</p>);
  return <>{nodes}</>;
}

/** What the model is writing right now (code or answer), refreshed about twice a second while a call is open. */
export function LiveDraft({ text }: { text: string }) {
  const { t } = useI18n();
  // the answer itself is shown as it is written, formatted like the final one, instead of as a line of code
  const at = text.indexOf("<solution>");
  if (at >= 0) {
    const body = text.slice(at + "<solution>".length).replace(/<\/solution>[\s\S]*$/, "").trim();
    if (body) {
      // exactly the final answer's layout, so the text simply grows in place and nothing changes when it finishes
      return (
        <section data-answer aria-live="polite">
          <div className="md">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{body}</ReactMarkdown>
          </div>
        </section>
      );
    }
  }
  const clean = text
    .replace(/<\/?(execute|solution|observation)>/g, "\n")
    .replace(/^\s+/, "")
    .slice(-700);
  if (!clean.trim()) return null;
  const writingCode = /<execute>/.test(text) && !/<\/execute>/.test(text);
  return (
    <div className="rounded-lg border border-dashed border-line bg-panel px-3 py-2">
      <p className="mb-1 flex items-center gap-2 text-xs text-soft">
        <span className="pulse inline-block h-1.5 w-1.5 rounded-full bg-accent" />
        {writingCode ? t("Writing code…") : t("Writing…")}
      </p>
      <pre className="max-h-40 overflow-hidden whitespace-pre-wrap break-words font-mono text-[12.5px] leading-snug text-soft">{clean}</pre>
    </div>
  );
}
