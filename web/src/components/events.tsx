"use client";

import { useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AnswerCard } from "@/components/answer";
import { CodeBlock } from "@/components/code";
import { usePreview } from "@/components/file-preview";
import { fileUrl, type AgentEvent, type Artifact, type PlanStep } from "@/lib/api";
import type { Source } from "@/lib/citations";
import { tr, useI18n } from "@/lib/i18n";

/** Human-readable name for a tool the model ran by itself. */
function toolName(tool: string): string {
  if (tool === "web_search") return tr("Web search");
  if (tool === "shell") return tr("Shell");
  if (tool.startsWith("codex_apps.")) return tr("ChatGPT app · {name}", { name: tool.slice("codex_apps.".length).replace(".", " · ") });
  return tr("Tool {name}", { name: tool });
}

/** First non-empty line, shortened, for folded summaries. */
export function preview(text: string, max = 70) {
  const line = text.split(/\r?\n/).map((l) => l.trim()).find(Boolean) ?? "";
  return line.length > max ? `${line.slice(0, max)}…` : line;
}

export function seconds(n?: number) {
  return n === undefined ? "" : ` · ${n.toFixed(1)}s`;
}

export function CopyButton({ text, label }: { text: string; label?: string }) {
  const { t } = useI18n();
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      className="text-xs text-soft hover:text-ink"
      onClick={async () => {
        await navigator.clipboard.writeText(text);
        setDone(true);
        setTimeout(() => setDone(false), 1200);
      }}
    >
      {done ? t("Copied") : (label ?? t("Copy"))}
    </button>
  );
}

const TAG_STYLE = {
  reasoning: "bg-codebg text-soft",
  code: "bg-accent-soft text-accent",
  output: "bg-codebg text-ink",
  tool: "bg-accent-soft text-accent",
  error: "bg-codebg text-warn",
} as const;

function Fold({
  title,
  children,
  open = false,
  tag,
  tone = "reasoning",
}: {
  title: string;
  children: React.ReactNode;
  open?: boolean;
  tag?: string;
  tone?: keyof typeof TAG_STYLE;
}) {
  return (
    <details open={open} className={`group rounded-lg border bg-card ${tone === "error" ? "border-warn" : "border-line"}`}>
      <summary className="cursor-pointer select-none break-words px-3 py-2 text-sm text-soft marker:content-none [overflow-wrap:anywhere]">
        <span className="mr-2 inline-block text-xs transition-transform group-open:rotate-90">▸</span>
        {tag && <span className={`mr-2 rounded px-1.5 py-0.5 text-xs ${TAG_STYLE[tone]}`}>{tag}</span>}
        {title}
      </summary>
      <div className="border-t border-line px-3 py-2">{children}</div>
    </details>
  );
}

/** Output that looks like a Python failure, so the step can be flagged. */
export function looksFailed(text: string): boolean {
  return /Traceback \(most recent call last\)|^\s*Error[: ]|\b(?:\w+Error|Exception):/m.test(text);
}

export function ArtifactLink({ a }: { a: Artifact }) {
  const { t } = useI18n();
  const open = usePreview();
  const onClick = (e: React.MouseEvent) => {
    if (open && !e.ctrlKey && !e.metaKey) {
      e.preventDefault();
      open(a);
    }
  };
  if (a.kind === "image") {
    return (
      <a href={fileUrl(a.path)} target="_blank" rel="noreferrer" className="block" onClick={onClick}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={fileUrl(a.path)} alt={a.name} className="max-h-60 rounded-md border border-line bg-white" />
        <span className="mt-0.5 block truncate text-xs text-soft">{a.name}</span>
      </a>
    );
  }
  const icon = { pdf: "PDF", table: "Table", html: "Page", text: "Text" }[a.kind as "pdf" | "table" | "html" | "text"];
  return (
    <a
      href={fileUrl(a.path)}
      target="_blank"
      rel="noreferrer"
      onClick={onClick}
      className="flex items-center gap-2 rounded-md border border-line bg-card px-2.5 py-1.5 text-sm hover:border-accent"
    >
      <span className="rounded bg-codebg px-1.5 text-xs text-soft">{t(icon)}</span>
      <span className="truncate">{a.name}</span>
    </a>
  );
}

/** The whole working trace as one folded bar (open while the task runs), instead of a column of cards. */
export function ProcessGroup({ items, live, children }: { items: AgentEvent[]; live: boolean; children: React.ReactNode }) {
  const { t } = useI18n();
  const box = useRef<HTMLDivElement>(null);
  const steps = items.filter((e) => e.type === "code" || e.type === "tool").length;
  const failed = items.filter((e) => e.type === "observation" && looksFailed(e.text)).length;
  const secs = items.reduce((n, e) => n + (e.type === "code" || e.type === "observation" ? (e.elapsed ?? 0) : 0), 0);
  const setAll = (open: boolean) => box.current?.querySelectorAll("details").forEach((d) => (d.open = open));
  return (
    <details open={live} className="group rounded-lg border border-line bg-panel">
      <summary className="cursor-pointer select-none px-3 py-2 text-sm text-soft marker:content-none">
        <span className="mr-2 inline-block text-xs transition-transform group-open:rotate-90">▸</span>
        {live ? t("Working steps (in progress)") : t("Show working steps")}
        {steps > 0 && ` · ${t("{n} steps", { n: steps })}`}
        {secs > 0 && ` · ${t("{n} s", { n: secs.toFixed(0) })}`}
        {failed > 0 && <span className="ml-2 rounded bg-codebg px-1.5 py-0.5 text-xs text-warn">{t("{n} steps failed", { n: failed })}</span>}
      </summary>
      <div className="border-t border-line p-3">
        <div className="mb-2 flex justify-end gap-3 text-xs text-soft">
          <button type="button" onClick={() => setAll(true)} className="hover:text-accent">
            {t("Expand all")}
          </button>
          <button type="button" onClick={() => setAll(false)} className="hover:text-accent">
            {t("Collapse all")}
          </button>
        </div>
        <div ref={box} className="space-y-2">
          {children}
        </div>
      </div>
    </details>
  );
}

export function PlanView({ steps, live = false }: { steps: PlanStep[]; live?: boolean }) {
  const { t } = useI18n();
  const mark = { todo: "○", done: "✓", failed: "✗" } as const;
  const color = { todo: "text-soft", done: "text-accent", failed: "text-warn" } as const;
  const current = live ? steps.findIndex((s) => s.status === "todo") : -1;
  return (
    <ol className="space-y-1.5 text-sm">
      {steps.map((s, i) => (
        <li key={i} className="flex gap-2" aria-current={i === current ? "step" : undefined}>
          {s.status === "done" ? (
            <span className="mt-0.5 grid h-4 w-4 shrink-0 place-items-center rounded-full bg-accent text-[10px] leading-none text-white dark:text-black" aria-label={t("Done")}>
              ✓
            </span>
          ) : (
            <span className={`${i === current ? "pulse text-accent" : color[s.status]} w-4 shrink-0 text-center`}>{i === current ? "▶" : mark[s.status]}</span>
          )}
          <span className={s.status === "done" ? "text-soft line-through decoration-line" : i === current ? "font-medium" : ""}>{s.text}</span>
        </li>
      ))}
    </ol>
  );
}

export function EventView({
  ev,
  onReview,
  reviewing,
  hasReview,
  ledger = [],
  turnId = "",
  onFork,
  vote,
  onVote,
  callInfo,
  media,
  onRevise,
}: {
  ev: AgentEvent;
  ledger?: Source[];
  onReview?: () => void;
  reviewing?: boolean;
  hasReview?: boolean;
  turnId?: string;
  onFork?: (text: string) => void;
  vote?: "up" | "down" | null;
  onVote?: (v: "up" | "down" | null) => void;
  callInfo?: string;
  media?: Artifact[];
  onRevise?: () => void;
}) {
  const { t } = useI18n();
  switch (ev.type) {
    case "reasoning":
      return (
        <Fold tag={t("Reasoning")} title={preview(ev.text)}>
          <p className="whitespace-pre-wrap text-sm">{ev.text}</p>
        </Fold>
      );
    case "code":
      return (
        <Fold tag={t("Code")} tone="code" title={`${ev.language}${seconds(ev.elapsed)} — ${preview(ev.code)}`}>
          <div className="mb-1 flex justify-end">
            <CopyButton text={ev.code} />
          </div>
          <CodeBlock code={ev.code} />
        </Fold>
      );
    case "observation": {
      const long = ev.text.length > 4000;
      const arts = ev.artifacts ?? [];
      return (
        <div className="space-y-2">
          <Fold
            tag={looksFailed(ev.text) ? t("Error") : t("Output")}
            tone={looksFailed(ev.text) ? "error" : "output"}
            title={`${seconds(ev.elapsed).replace(" · ", "")}${arts.length ? ` · ${t("{n} artifacts", { n: arts.length })}` : ""} — ${preview(ev.text)}`}
          >
            <pre className="max-h-80 overflow-auto rounded-md bg-codebg p-3 font-mono text-[13px] leading-snug whitespace-pre-wrap">
              {long ? `${ev.text.slice(0, 4000)}\n${t("…(truncated, {n} characters in all)", { n: ev.text.length })}` : ev.text}
            </pre>
          </Fold>
          {arts.some((a) => a.kind === "image") && (
            <div className="flex flex-wrap gap-3">
              {arts
                .filter((a) => a.kind === "image")
                .map((a) => (
                  <ArtifactLink key={a.path} a={a} />
                ))}
            </div>
          )}
        </div>
      );
    }
    case "tool":
      return (
        <Fold tag={t("Tool")} tone="tool" title={`${toolName(ev.tool)}${ev.query ? ` — ${preview(ev.query, 60)}` : ""}`}>
          {ev.results && ev.results.length > 0 ? (
            <ul className="space-y-2">
              {ev.results.map((r, i) => (
                <li key={`${r.url}-${i}`} className="text-sm">
                  <a href={r.url} target="_blank" rel="noreferrer" className="font-medium text-accent underline">
                    {r.title || r.url}
                  </a>
                  <div className="text-xs text-soft">{r.domain}</div>
                  {r.snippet && <div className="text-xs text-soft">{r.snippet}</div>}
                </li>
              ))}
            </ul>
          ) : (
            <pre className="max-h-60 overflow-auto rounded-md bg-codebg p-3 font-mono text-[13px] whitespace-pre-wrap">{ev.text || t("(no output)")}</pre>
          )}
        </Fold>
      );
    case "notice":
      return <p className="text-sm text-warn">{ev.text}</p>;
    case "answer":
      return (
        <AnswerCard
          turnId={turnId}
          onFork={onFork}
          vote={vote}
          onVote={onVote}
          callInfo={callInfo}
          text={ev.text}
          fallback={ev.fallback}
          quick={ev.quick}
          ledger={ledger}
          media={media}
          onReview={onReview}
          reviewing={reviewing}
          hasReview={hasReview}
        />
      );
    case "review":
      return (
        <section className="rounded-xl border border-line bg-panel p-5">
          <h3 className="mb-1 font-serif text-base font-semibold">{t("Independent review")}</h3>
          <div className="md text-sm">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{ev.text}</ReactMarkdown>
          </div>
          {onRevise && (
            <button type="button" onClick={onRevise} className="mt-3 rounded-md border border-line bg-card px-3 py-1 text-sm hover:border-accent">
              {t("Revise per review")}
            </button>
          )}
        </section>
      );
    case "error":
      return <div className="rounded-lg border border-warn/50 bg-card p-3 text-sm text-warn">{t("Something went wrong: {message}", { message: ev.message })}</div>;
    case "cancelled":
      return <p className="text-sm text-soft">{t("Task stopped.")}</p>;
    default:
      return null;
  }
}
