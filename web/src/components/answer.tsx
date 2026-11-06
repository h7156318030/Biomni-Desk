"use client";

import { useMemo, useRef, useState } from "react";
import { ExportMenu } from "@/components/export-menu";
import ReactMarkdown, { defaultUrlTransform } from "react-markdown";
import remarkGfm from "remark-gfm";
import { fileUrl, type Artifact, type RefMeta } from "@/lib/api";
import { FileActions } from "@/components/file-actions";
import { numberCitations, type Reference, type Source } from "@/lib/citations";
import { useRefMeta } from "@/lib/use-ref-meta";
import { useI18n } from "@/lib/i18n";

/** Markdown drops addresses it does not know, which includes a Windows file path ("F:/…/chart.png"); those are kept, everything else is
 *  filtered as before (javascript: and similar stay blocked). The page only turns them into links to its own files endpoint. */
function localPathOk(url: string): string {
  return /^[a-z]:[\\/]/i.test(url) ? url : defaultUrlTransform(url);
}

function AnswerImage({ url, alt }: { url: string; alt: string }) {
  const { t } = useI18n();
  const [failed, setFailed] = useState(false);
  if (failed)
    return (
      <span className="my-1 inline-block text-xs text-soft">{alt ? t("(image cannot be displayed: {alt})", { alt }) : t("(image cannot be displayed)")}</span>
    );
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={url} alt={alt} onError={() => setFailed(true)} className="my-2 max-h-[28rem] max-w-full rounded-md border border-line bg-white" />;
}

const VIDEO = /\.(mp4|webm|mov)(\?|#|$)/i;

/** A picture or video the answer points at: web addresses as they are, a file on this machine through the files endpoint. */
function mediaUrl(src: string): string {
  if (/^(https?:|data:|blob:)/i.test(src)) return src;
  return fileUrl(src);
}

const KIND_LABEL = { paper: "Paper", db: "Database", web: "Web" } as const;

/** "https://www.example.org/a/b/c" -> "example.org/a/b/c", cut to `max` characters like the inline chips. */
export function shortUrl(href: string | undefined, max = 24): string {
  if (!href) return "";
  const s = href.replace(/^https?:\/\/(www\.)?/, "").replace(/\/$/, "");
  return s.length > max ? `${s.slice(0, max)}…` : s;
}

/** What the inline chip says: a short, recognisable name for the source (not a truncated host name). */
function chipLabel(href: string, ref?: Reference): string {
  if (ref?.key.startsWith("pmid:")) return `PubMed ${ref.key.slice(5)}`;
  if (ref?.key.startsWith("doi:")) return shortUrl(`doi.org/${ref.key.slice(4)}`, 26);
  if (ref?.kind === "db") return ref.label;
  return shortUrl(href, 26);
}

function Favicon({ href }: { href?: string }) {
  // A neutral dot instead of fetching icons from a third-party service for every cited site.
  return <span aria-hidden="true" className="inline-block h-3.5 w-3.5 rounded-full bg-accent-soft align-[-2px]" title={href ? new URL(href, "http://x").hostname : ""} />;
}

/** Inline citation: a small rounded chip with the shortened address, right after the claim it supports. */
function CitationChip({ href, refItem, meta }: { href: string; refItem?: Reference; meta?: RefMeta }) {
  const { t } = useI18n();
  const title = meta?.title || refItem?.title || refItem?.label || href;
  const byline = [meta?.authors, meta?.journal, meta?.year].filter(Boolean).join(" · ");
  return (
    <span className="group/cite relative mx-0.5 inline-block align-baseline">
      <a
        href={href}
        target="_blank"
        rel="noreferrer"
        className="inline-block max-w-[16rem] truncate rounded-full border border-line bg-card px-2 py-px align-middle text-[12px] leading-[1.35] text-soft no-underline hover:border-accent hover:text-ink"
      >
        {chipLabel(href, refItem)}
      </a>
      <span className="pointer-events-none invisible absolute bottom-full left-0 z-30 mb-1.5 w-80 max-w-[80vw] rounded-lg border border-line bg-card p-3 text-left text-xs font-normal leading-snug text-ink opacity-0 shadow-xl transition-opacity group-hover/cite:visible group-hover/cite:opacity-100">
        <span className="mb-1 block text-[11px] text-soft">
          {t("Source")}
          {refItem?.weak ? t(" · not in this run's tool output") : ""}
        </span>
        <span className="flex gap-2">
          <Favicon href={href} />
          <span className="min-w-0">
            <span className="block text-sm font-medium leading-snug">
              {refItem ? `${refItem.n}. ` : ""}
              {title}
            </span>
            {byline && <span className="mt-0.5 block text-soft">{byline}</span>}
            <span className="mt-0.5 block break-all text-soft">{shortUrl(href, 60)}</span>
          </span>
        </span>
      </span>
    </span>
  );
}

function References({ refs, meta }: { refs: Reference[]; meta: Record<string, RefMeta> }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  if (!refs.length) return null;
  const bad = refs.filter((r) => !r.verified && !r.weak).length;
  return (
    <div className="mt-3">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-1.5 rounded-full border border-line bg-card px-3 py-1 text-sm hover:border-accent"
        aria-expanded={open}
      >
        {t("References")} <span className="text-soft">({refs.length})</span>
        <span className={`text-xs text-soft transition-transform ${open ? "rotate-180" : ""}`}>⌃</span>
      </button>
      {bad > 0 && <span className="ml-2 text-xs text-warn">{t("{n} could not be verified", { n: bad })}</span>}
      {open && (
        <ol className="mt-4 space-y-4 text-[15px]">
          {refs.map((r) => {
            const m = meta[r.key];
            const ok = r.verified || r.weak;
            const title = m?.title || r.title || r.label;
            const byline = [m?.authors, m?.journal, m?.year].filter(Boolean).join(" · ");
            return (
              <li key={r.n} className="flex gap-2">
                <span className={`w-6 shrink-0 text-right ${ok ? "text-soft" : "text-warn"}`}>{r.n}.</span>
                <div className="min-w-0 flex-1">
                  {ok ? (
                    <a href={r.href} target="_blank" rel="noreferrer" className="break-words leading-snug text-ink hover:text-accent">
                      {title}
                    </a>
                  ) : (
                    <span className="break-words text-warn">
              {`${r.label}${t("(could not be verified: not found in tool output, PubMed, Crossref or the web; do not rely on it)")}`}
                    </span>
                  )}
                  {ok && (
                    <div className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-soft">
                      <span aria-hidden="true">↗</span>
                      <span className="break-all">{shortUrl(r.href, 60)}</span>
                      <span className="rounded bg-codebg px-1.5">{t(KIND_LABEL[r.kind])}</span>
                      {r.weak && <span className="rounded bg-codebg px-1.5">{t("not in this run's tool output, but confirmed to exist")}</span>}
                    </div>
                  )}
                  {ok && byline && <div className="text-xs text-soft">{byline}</div>}
                  {ok && m?.doi && (
                    <a href={`https://doi.org/${m.doi}`} target="_blank" rel="noreferrer" className="text-xs text-accent underline">
                      DOI {m.doi}
                    </a>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}

function IconButton({ label, onClick, active, disabled, children }: { label: string; onClick?: () => void; active?: boolean; disabled?: boolean; children: React.ReactNode }) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      onClick={onClick}
      disabled={disabled}
      className={`rounded-md px-1.5 py-1 text-soft hover:bg-card hover:text-ink disabled:opacity-40 ${active ? "text-accent" : ""}`}
    >
      {children}
    </button>
  );
}

/** The assistant's answer as plain text on the page (no card), with the action row and the References pill under it. */
export function AnswerCard({
  text,
  fallback,
  quick,
  ledger,
  onReview,
  reviewing,
  hasReview,
  onSaveSkill,
  onFork,
  vote = null,
  onVote,
  callInfo = "",
  media = [],
}: {
  turnId: string;
  text: string;
  fallback?: boolean;
  quick?: boolean;
  ledger: Source[];
  onReview?: () => void;
  reviewing?: boolean;
  hasReview?: boolean;
  onSaveSkill?: () => void;
  onFork?: (text: string) => void;
  vote?: "up" | "down" | null;
  onVote?: (v: "up" | "down" | null) => void;
  callInfo?: string;
  media?: Artifact[];
}) {
  const { t } = useI18n();
  const first = useMemo(() => numberCitations(text, ledger), [text, ledger]);
  const meta = useRefMeta(first.refs);
  const withTitles = useMemo(
    () => ledger.map((s) => (meta[s.key]?.title ? { ...s, title: meta[s.key].title } : s)),
    [ledger, meta],
  );
  const cited = useMemo(() => numberCitations(text, withTitles, meta), [text, withTitles, meta]);

  const components = useMemo(
    () => ({
      img: ({ src, alt }: { src?: string | Blob; alt?: string }) => {
        const url = typeof src === "string" ? mediaUrl(src) : "";
        return url ? <AnswerImage url={url} alt={alt ?? ""} /> : null;
      },
      a: ({ href, children }: { href?: string; children?: React.ReactNode }) => {
        if (href && VIDEO.test(href)) {
          return <video src={mediaUrl(href)} controls preload="metadata" className="my-2 max-h-[28rem] max-w-full rounded-md border border-line" />;
        }
        if (href === "#unverified") {
          return (
            <span className="font-medium text-warn" title={t("Could not verify: this source is not in the tool output")}>
              {children}
            </span>
          );
        }
        // a link to a file the agent made (a deck, a table): served by the files endpoint, opens as a download
        if (href && (/^[a-z]:[\\/]/i.test(href) || /^[^:#?\s]+\.(pptx|xlsx|docx|csv|tsv|pdf|png|jpe?g|gif|html|md|txt|zip)$/i.test(href))) {
          return (
            <span className="inline-flex flex-wrap items-baseline gap-x-3">
              <a href={fileUrl(href)} target="_blank" rel="noreferrer">
                {children}
              </a>
              <FileActions path={href} compact />
            </span>
          );
        }
        const label = Array.isArray(children) ? children.join("") : String(children ?? "");
        const m = /^\[(\d+)\]$/.exec(label);
        if (!m || !href) {
          return (
            <a href={href} target="_blank" rel="noreferrer">
              {children}
            </a>
          );
        }
        const refItem = cited.refs[Number(m[1]) - 1];
        return <CitationChip href={href} refItem={refItem} meta={refItem ? meta[refItem.key] : undefined} />;
      },
    }),
    [cited.refs, meta, t],
  );

  const [copied, setCopied] = useState(false);
  const section = useRef<HTMLElement>(null);
  const choose = (v: "up" | "down") => onVote?.(vote === v ? null : v);

  return (
    <section ref={section} data-answer>
      {fallback && <p className="mb-1 text-xs text-soft">{t("(no formal answer marker was received; the model's raw output follows)")}</p>}
      {quick && (
        <p className="mb-1 text-xs text-soft">
          {t(
            "Quick answer: from the model's own knowledge, with no search and no tools run. If you need it checked, say in your question that literature or data should be looked up.",
          )}
        </p>
      )}
      <div className="md">
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={components} urlTransform={localPathOk}>
          {cited.markdown}
        </ReactMarkdown>
      </div>
      {media.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-3">
          {media.map((a) =>
            a.kind === "video" ? (
              <figure key={a.path} className="max-w-full">
                <video src={fileUrl(a.path)} controls preload="metadata" className="max-h-[28rem] max-w-full rounded-md border border-line" />
                <figcaption className="mt-0.5 truncate text-xs text-soft">{a.name}</figcaption>
              </figure>
            ) : (
              <figure key={a.path} className="max-w-full">
                <a href={fileUrl(a.path)} target="_blank" rel="noreferrer">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={fileUrl(a.path)} alt={a.name} className="max-h-[28rem] max-w-full rounded-md border border-line bg-white" />
                </a>
                <figcaption className="mt-0.5 truncate text-xs text-soft">{a.name}</figcaption>
              </figure>
            ),
          )}
        </div>
      )}
      <References refs={cited.refs} meta={meta} />
      <div className="mt-3 flex flex-wrap items-center gap-1 text-sm">
        {onReview && (
          <button
            type="button"
            onClick={onReview}
            disabled={reviewing || hasReview}
            className="rounded-md px-2 py-1 text-soft hover:bg-card hover:text-ink disabled:opacity-50"
          >
            ☑ {reviewing ? t("Reviewing…") : hasReview ? t("Reviewed") : t("Review")}
          </button>
        )}
        {onSaveSkill && (
          <button type="button" onClick={onSaveSkill} className="rounded-md px-2 py-1 text-soft hover:bg-card hover:text-ink">
            ✦ {t("Save as a skill")}
          </button>
        )}
        <span className="mx-1 h-4 w-px bg-line" />
        <IconButton label={t("Helpful")} onClick={() => choose("up")} active={vote === "up"}>
          👍
        </IconButton>
        <IconButton label={t("Not helpful")} onClick={() => choose("down")} active={vote === "down"}>
          👎
        </IconButton>
        <IconButton
          label={t("Copy answer")}
          onClick={async () => {
            await navigator.clipboard.writeText(text);
            setCopied(true);
            setTimeout(() => setCopied(false), 1200);
          }}
        >
          {copied ? "✓" : "⧉"}
        </IconButton>
        <ExportMenu markdown={cited.markdown} refs={cited.refs} meta={meta} target={section} />
        <span className="mx-1 h-4 w-px bg-line" />
        {onFork && (
          <button type="button" onClick={() => onFork(text)} className="rounded-md px-2 py-1 text-soft hover:bg-card hover:text-ink">
            {t("⑂ Start a new task from here")}
          </button>
        )}
        {callInfo && (
          <span className="ml-auto truncate text-xs text-soft" title={t("What the model calls in this task actually used (reported by the server)")}>
            {callInfo}
          </span>
        )}
      </div>
    </section>
  );
}
