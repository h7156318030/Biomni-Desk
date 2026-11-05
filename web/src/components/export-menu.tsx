"use client";

import { useRef } from "react";
import type { RefMeta } from "@/lib/api";
import type { Reference } from "@/lib/citations";
import { currentLang, tr, useI18n } from "@/lib/i18n";

/** The answer plus a numbered reference list, as a standalone Markdown document. */
export function buildMarkdown(markdown: string, refs: Reference[], meta: Record<string, RefMeta>): string {
  if (!refs.length) return markdown.trim() + "\n";
  const zh = currentLang() === "zh";
  const stop = zh ? "。" : ". ";
  const comma = zh ? "，" : ", ";
  const lines = refs.map((r) => {
    const m = meta[r.key];
    const title = m?.title || r.title || r.label;
    const byline = [m?.authors, m?.journal, m?.year].filter(Boolean).join(comma);
    const status = r.verified || r.weak ? "" : tr("(unverified)");
    return `${r.n}. ${title}${byline ? `${stop}${byline}` : ""}${r.href ? `${stop}${r.href}` : ""}${status}`;
  });
  return `${markdown.trim()}\n\n## ${tr("References")}\n\n${lines.join("\n")}\n`;
}

/** Markdown with the link syntax and emphasis removed, for pasting into a plain text field. */
export function toPlainText(markdown: string): string {
  return markdown
    .replace(/\[([^\]]+)\]\((https?:[^)]+)\)/g, (_m, label: string, url: string) => (/^\[?\d+\]?$/.test(label) ? `[${label.replace(/\D/g, "")}]` : `${label} (${url})`))
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/(\*\*|__)(.*?)\1/g, "$2")
    .replace(/(^|[^*])\*(?!\s)([^*\n]+)\*/g, "$1$2")
    .replace(/`([^`]+)`/g, "$1")
    .trim();
}

/** Every GFM table in the Markdown, as rows of cells (the separator row is dropped). */
export function extractTables(markdown: string): string[][][] {
  const tables: string[][][] = [];
  let cur: string[][] | null = null;
  for (const raw of markdown.split(/\r?\n/)) {
    const line = raw.trim();
    if (line.startsWith("|") && line.endsWith("|") && line.length > 1) {
      const cells = line.slice(1, -1).split("|").map((c) => c.trim());
      if (cells.every((c) => /^:?-{2,}:?$/.test(c))) continue;
      (cur ??= []).push(cells);
    } else if (cur) {
      tables.push(cur);
      cur = null;
    }
  }
  if (cur) tables.push(cur);
  return tables;
}

export function toCsv(rows: string[][]): string {
  const q = (v: string) => (/[",\n\r]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v);
  return rows.map((r) => r.map(q).join(",")).join("\r\n") + "\r\n";
}

function download(name: string, text: string, mime: string, bom = false) {
  const url = URL.createObjectURL(new Blob([bom ? "﻿" : "", text], { type: `${mime};charset=utf-8` }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function ExportMenu({
  markdown,
  refs,
  meta,
  target,
}: {
  markdown: string;
  refs: Reference[];
  meta: Record<string, RefMeta>;
  target: React.RefObject<HTMLElement | null>;
}) {
  const { t } = useI18n();
  const menu = useRef<HTMLDetailsElement>(null);
  const tables = extractTables(markdown);
  const stamp = new Date().toISOString().slice(0, 10);
  const close = () => menu.current?.removeAttribute("open");

  const print = () => {
    const el = target.current;
    close();
    if (!el) return;
    el.classList.add("print-answer");
    const done = () => {
      el.classList.remove("print-answer");
      window.removeEventListener("afterprint", done);
    };
    window.addEventListener("afterprint", done);
    window.print();
  };

  const item = "block w-full px-3 py-1.5 text-left text-sm hover:bg-accent-soft";
  return (
    <details ref={menu} className="relative">
      <summary className="cursor-pointer list-none rounded-md px-2 py-1 text-soft marker:content-none hover:bg-card hover:text-ink">{t("⇩ Export")}</summary>
      <div className="absolute bottom-full left-0 z-20 mb-1 w-52 overflow-hidden rounded-xl border border-line bg-panel py-1 shadow-lg">
        <button
          type="button"
          className={item}
          onClick={() => {
            download(`${tr("answer")}-${stamp}.md`, buildMarkdown(markdown, refs, meta), "text/markdown");
            close();
          }}
        >
          {t("Download Markdown")}
        </button>
        <button
          type="button"
          className={item}
          onClick={async () => {
            await navigator.clipboard.writeText(toPlainText(buildMarkdown(markdown, refs, meta)));
            close();
          }}
        >
          {t("Copy as plain text")}
        </button>
        <button type="button" className={item} onClick={print}>
          {t("Print / save as PDF")}
        </button>
        {tables.map((tb, i) => (
          <button
            key={i}
            type="button"
            className={item}
            onClick={() => {
              download(`${tr("table")}${i + 1}-${stamp}.csv`, toCsv(tb), "text/csv", true);
              close();
            }}
          >
            {t("Download table{suffix} (CSV)", { suffix: tables.length > 1 ? ` ${i + 1}` : "" })}
          </button>
        ))}
      </div>
    </details>
  );
}
