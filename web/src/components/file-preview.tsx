"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { fileUrl, type Artifact } from "@/lib/api";
import { FileActions } from "@/components/file-actions";
import { useI18n } from "@/lib/i18n";

/** Lets any artifact link in the page open the preview instead of a new tab. */
export const PreviewContext = createContext<((a: Artifact) => void) | null>(null);
export const usePreview = () => useContext(PreviewContext);

/** CSV / TSV text -> rows. Quotes may hold the delimiter, newlines and doubled quotes. */
export function parseDelimited(text: string, delimiter: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let quoted = false;
  const src = text.replace(/^﻿/, "");
  for (let i = 0; i < src.length; i++) {
    const ch = src[i];
    if (quoted) {
      if (ch === '"' && src[i + 1] === '"') {
        cell += '"';
        i++;
      } else if (ch === '"') quoted = false;
      else cell += ch;
    } else if (ch === '"' && cell === "") quoted = true;
    else if (ch === delimiter) {
      row.push(cell);
      cell = "";
    } else if (ch === "\n" || ch === "\r") {
      if (ch === "\r" && src[i + 1] === "\n") i++;
      row.push(cell);
      rows.push(row);
      row = [];
      cell = "";
    } else cell += ch;
  }
  if (cell !== "" || row.length) {
    row.push(cell);
    rows.push(row);
  }
  return rows;
}

const MAX_ROWS = 200;
const MAX_BYTES = 400_000;

function extOf(name: string) {
  return name.slice(name.lastIndexOf(".") + 1).toLowerCase();
}

function TextBody({ file }: { file: Artifact }) {
  const { t } = useI18n();
  const [state, setState] = useState<{ path: string; text?: string; error?: string } | null>(null);
  const ext = extOf(file.name);
  const BINARY = ["pptx", "docx", "zip", "gz", "h5ad"]; // kind "text" in the file list, but not text
  const readable = (file.kind === "text" && !BINARY.includes(ext)) || (file.kind === "table" && ["csv", "tsv", "txt"].includes(ext));

  useEffect(() => {
    if (!readable) return;
    let alive = true;
    fetch(fileUrl(file.path))
      .then((r) => (r.ok ? r.text() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((txt) => alive && setState({ path: file.path, text: txt.slice(0, MAX_BYTES) }))
      .catch((e) => alive && setState({ path: file.path, error: String(e) }));
    return () => {
      alive = false;
    };
  }, [file.path, readable]);

  if (!readable)
    return (
      <div className="space-y-3 p-6 text-sm text-soft">
        <p>{t("This file cannot be previewed on the page. You can open it with a program on this computer:")}</p>
        <FileActions path={file.path} />
      </div>
    );
  if (!state || state.path !== file.path) return <p className="p-6 text-sm text-soft">{t("Loading…")}</p>;
  if (state.error) return <p className="p-6 text-sm text-warn">{t("Failed to read: {error}", { error: state.error })}</p>;
  const text = state.text ?? "";

  if (file.kind === "table" && ext !== "txt") {
    const rows = parseDelimited(text, ext === "tsv" ? "\t" : ",");
    const [head, ...body] = rows;
    return (
      <div className="overflow-auto">
        <table className="min-w-full border-collapse text-sm">
          <thead className="sticky top-0 bg-panel">
            <tr>
              {head?.map((h, i) => (
                <th key={i} className="border border-line px-2 py-1 text-left font-medium">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {body.slice(0, MAX_ROWS).map((r, i) => (
              <tr key={i}>
                {r.map((c, j) => (
                  <td key={j} className="border border-line px-2 py-1">
                    {c}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        <p className="p-2 text-xs text-soft">
          {t("{n} rows in all{suffix}", {
            n: body.length,
            suffix: body.length > MAX_ROWS ? t(", only the first {max} rows shown", { max: MAX_ROWS }) : "",
          })}
        </p>
      </div>
    );
  }
  return <pre className="overflow-auto whitespace-pre-wrap p-4 font-mono text-[13px] leading-snug">{text}</pre>;
}

export function FilePreview({ files, index, onIndex, onClose }: { files: Artifact[]; index: number; onIndex: (i: number) => void; onClose: () => void }) {
  const { t } = useI18n();
  const file = files[index];
  const [fit, setFit] = useState(true);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      else if (e.key === "ArrowRight" && index < files.length - 1) onIndex(index + 1);
      else if (e.key === "ArrowLeft" && index > 0) onIndex(index - 1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [index, files.length, onIndex, onClose]);

  if (!file) return null;
  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-black/60 p-4 md:p-8" onClick={onClose} role="presentation">
      <div
        role="dialog"
        aria-label={t("Preview {name}", { name: file.name })}
        className="mx-auto flex min-h-0 w-full max-w-5xl flex-1 flex-col overflow-hidden rounded-xl border border-line bg-panel shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-3 border-b border-line px-4 py-2 text-sm">
          <span className="min-w-0 flex-1 truncate font-medium" title={file.name}>
            {file.name}
          </span>
          <span className="shrink-0 text-xs text-soft">
            {index + 1} / {files.length}
          </span>
          <button type="button" disabled={index === 0} onClick={() => onIndex(index - 1)} aria-label={t("Previous")} className="text-soft hover:text-accent disabled:opacity-30">
            ←
          </button>
          <button
            type="button"
            disabled={index >= files.length - 1}
            onClick={() => onIndex(index + 1)}
            aria-label={t("Next")}
            className="text-soft hover:text-accent disabled:opacity-30"
          >
            →
          </button>
          {file.kind === "image" && (
            <button type="button" onClick={() => setFit((f) => !f)} className="text-xs text-soft hover:text-accent">
              {fit ? t("Actual size") : t("Fit to window")}
            </button>
          )}
          <FileActions path={file.path} compact />
          <button type="button" onClick={onClose} aria-label={t("Close")} className="text-soft hover:text-accent">
            ✕
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-auto bg-card">
          {file.kind === "image" ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={fileUrl(file.path)} alt={file.name} className={fit ? "mx-auto max-h-full max-w-full object-contain p-2" : "p-2"} />
          ) : file.kind === "pdf" ? (
            <iframe src={fileUrl(file.path)} title={file.name} className="h-full min-h-[70vh] w-full" />
          ) : file.kind === "html" ? (
            <iframe src={fileUrl(file.path)} title={file.name} sandbox="" className="h-full min-h-[70vh] w-full bg-white" />
          ) : (
            <TextBody file={file} />
          )}
        </div>
      </div>
    </div>
  );
}
