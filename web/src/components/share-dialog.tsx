"use client";

import { useEffect, useState } from "react";
import { fileUrl, publishResult, publishedUrl, type Artifact } from "@/lib/api";
import { parseDelimited } from "@/components/file-preview";
import { CopyButton } from "@/components/events";
import { attachmentsHtml, buildShareHtml, cleanAnswerHtml, type Attachment } from "@/lib/share-html";
import { tr, useI18n } from "@/lib/i18n";

const MAX_IMAGE_BYTES = 800_000;
const MAX_TOTAL_BYTES = 1_400_000; // the server accepts up to 2,000,000 characters of HTML
const MAX_ROWS = 200;

function extOf(name: string) {
  return name.slice(name.lastIndexOf(".") + 1).toLowerCase();
}

function toDataUri(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result));
    r.onerror = () => reject(r.error);
    r.readAsDataURL(blob);
  });
}

/** Read one result file into something the standalone page can show. `budget` is what is left for embedded images. */
export async function loadAttachment(a: Artifact, budget: { left: number }): Promise<Attachment> {
  try {
    // no-store: an <img> of the same file may already be cached without CORS headers, and fetch() would fail on it
    const res = await fetch(fileUrl(a.path), { cache: "no-store" });
    if (!res.ok) return { name: a.name, kind: "skipped", why: tr("Could not read this file (HTTP {status}).", { status: res.status }) };
    if (a.kind === "image") {
      const blob = await res.blob();
      if (blob.size > MAX_IMAGE_BYTES || blob.size * 1.4 > budget.left) {
        return { name: a.name, kind: "skipped", why: tr("The image is too large, so it was not embedded in the page.") };
      }
      budget.left -= blob.size * 1.4;
      return { name: a.name, kind: "image", dataUri: await toDataUri(blob) };
    }
    if (a.kind === "table" && ["csv", "tsv"].includes(extOf(a.name))) {
      const rows = parseDelimited(await res.text(), extOf(a.name) === "tsv" ? "\t" : ",");
      return { name: a.name, kind: "table", rows: rows.slice(0, MAX_ROWS + 1), total: Math.max(0, rows.length - 1) };
    }
    if (a.kind === "text" || (a.kind === "table" && extOf(a.name) === "txt")) {
      return { name: a.name, kind: "text", text: (await res.text()).slice(0, 20000) };
    }
    return { name: a.name, kind: "skipped", why: tr("This file type is not embedded in the page; download it separately.") };
  } catch {
    return { name: a.name, kind: "skipped", why: tr("Error while reading.") };
  }
}

/** Every question and answer on the page as one list; the folded reference list is opened just long enough to copy. */
async function collectTurns(): Promise<{ prompt: string; answerHtml: string }[]> {
  const log = document.querySelector("[role=log]");
  const turns: { prompt: string; answerHtml: string }[] = [];
  if (!log) return turns;
  for (const el of Array.from(log.querySelectorAll("[data-turn]"))) {
    const prompt = el.querySelector("[data-prompt]")?.textContent?.trim() ?? "";
    const parts: string[] = [];
    for (const section of Array.from(el.querySelectorAll("[data-answer]"))) {
      const md = section.querySelector(".md");
      if (md) parts.push(cleanAnswerHtml(md));
      // the references toggle is labelled in the UI language, so either wording is accepted
      const pill = Array.from(section.querySelectorAll("button")).find((b) => /References|参考文献/.test(b.textContent ?? ""));
      if (pill) {
        const wasClosed = pill.getAttribute("aria-expanded") === "false";
        if (wasClosed) {
          pill.click();
          await new Promise((r) => setTimeout(r, 60));
        }
        const list = pill.parentElement?.querySelector("ol");
        if (list) {
          const box = document.createElement("div");
          box.appendChild(list.cloneNode(true));
          parts.push(`<h3>${tr("References")}</h3>${cleanAnswerHtml(box)}`);
        }
        if (wasClosed) pill.click();
      }
    }
    const answerHtml = parts.join("\n");
    if (prompt || answerHtml) turns.push({ prompt, answerHtml });
  }
  return turns;
}

type Mode = "publish" | "download";

export function ShareDialog({
  title,
  taskId,
  artifacts,
  onClose,
  onPublished,
}: {
  title: string;
  taskId: string;
  artifacts: Artifact[];
  onClose: () => void;
  onPublished: () => void;
}) {
  const { t } = useI18n();
  const [mode, setMode] = useState<Mode>("publish");
  const [withFiles, setWithFiles] = useState(artifacts.length > 0);
  const [chosen, setChosen] = useState<string[]>(artifacts.map((a) => a.path));
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; text: string; url?: string } | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const create = async () => {
    setBusy(true);
    setResult(null);
    try {
      const turns = await collectTurns();
      if (!turns.some((x) => x.answerHtml)) {
        setResult({ ok: false, text: tr("This task has no answer to share yet.") });
        return;
      }
      let extra = "";
      if (withFiles && chosen.length) {
        const budget = { left: MAX_TOTAL_BYTES };
        const items: Attachment[] = [];
        for (const a of artifacts.filter((x) => chosen.includes(x.path))) items.push(await loadAttachment(a, budget));
        extra = attachmentsHtml(items);
      }
      const html = buildShareHtml(title, turns, new Date(), extra);
      if (mode === "download") {
        const url = URL.createObjectURL(new Blob([html], { type: "text/html;charset=utf-8" }));
        const a = document.createElement("a");
        a.href = url;
        a.download = `${title.replace(/[\\/:*?"<>|]/g, "_").slice(0, 40) || tr("answer")}.html`;
        a.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        setResult({ ok: true, text: tr("Downloaded the HTML file. You can send it to anyone to open in a browser.") });
      } else {
        const r = await publishResult({ title, html, task_id: taskId });
        onPublished();
        setResult({ ok: true, text: tr("Published to the drive under “Published results”."), url: publishedUrl(r.id) });
      }
    } catch (e) {
      setResult({ ok: false, text: e instanceof Error ? e.message : String(e) });
    } finally {
      setBusy(false);
    }
  };

  const radio = "flex cursor-pointer items-start gap-2 rounded-lg border p-3 text-sm";
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" onClick={onClose} role="presentation">
      <div role="dialog" aria-label={t("Share conversation")} className="w-full max-w-md rounded-2xl border border-line bg-panel p-5 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="font-serif text-lg font-semibold">{t("Share conversation")}</h2>
            <p className="truncate text-sm text-soft">{title}</p>
          </div>
          <button type="button" onClick={onClose} aria-label={t("Close")} className="text-soft hover:text-accent">
            ✕
          </button>
        </div>
        <p className="mt-3 text-sm text-soft">
          {t("Turn this conversation's questions, answers and references into a standalone web page (no scripts). Anyone can view it without signing in.")}
        </p>

        <fieldset className="mt-4 space-y-2">
          <legend className="mb-1 text-xs font-medium text-soft">{t("Mode")}</legend>
          <label className={`${radio} ${mode === "publish" ? "border-accent bg-accent-soft" : "border-line"}`}>
            <input type="radio" name="mode" checked={mode === "publish"} onChange={() => setMode("publish")} className="mt-1" />
            <span>
              {t("Publish to the drive")}
              <span className="block text-xs text-soft">
                {t("Saved under “Published results”, giving you a link (openable on this machine and on the same local network).")}
              </span>
            </span>
          </label>
          <label className={`${radio} ${mode === "download" ? "border-accent bg-accent-soft" : "border-line"}`}>
            <input type="radio" name="mode" checked={mode === "download"} onChange={() => setMode("download")} className="mt-1" />
            <span>
              {t("Download the HTML file only")}
              <span className="block text-xs text-soft">{t("Not saved to the drive; the file can be sent to anyone.")}</span>
            </span>
          </label>
        </fieldset>

        <div className="mt-4">
          <label className="flex cursor-pointer items-center gap-2 text-sm">
            <input type="checkbox" checked={withFiles} disabled={!artifacts.length} onChange={(e) => setWithFiles(e.target.checked)} />
            {t("Include generated files")}
            {!artifacts.length && <span className="text-xs text-soft">{t("(this task produced no files)")}</span>}
          </label>
          {withFiles && artifacts.length > 0 && (
            <>
              <p className="mt-1 text-xs text-soft">
                {t("Images are embedded in the page, tables and text are shown directly; other types are not embedded.")}
              </p>
              <ul className="mt-2 max-h-40 space-y-0.5 overflow-y-auto rounded-lg border border-line bg-card p-2 text-sm">
                {artifacts.map((a) => (
                  <li key={a.path}>
                    <label className="flex cursor-pointer items-center gap-2">
                      <input
                        type="checkbox"
                        checked={chosen.includes(a.path)}
                        onChange={() => setChosen((c) => (c.includes(a.path) ? c.filter((x) => x !== a.path) : [...c, a.path]))}
                      />
                      <span className="truncate" title={a.name}>
                        {a.name}
                      </span>
                    </label>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>

        {result && (
          <p className={`mt-3 text-sm ${result.ok ? "text-accent" : "text-warn"}`}>
            {result.text}{" "}
            {result.url && (
              <>
                <a href={result.url} target="_blank" rel="noreferrer" className="underline">
                  {t("Open")}
                </a>{" "}
                <CopyButton text={result.url} label={t("Copy link")} />
              </>
            )}
          </p>
        )}

        <button type="button" disabled={busy} onClick={create} className="mt-4 w-full rounded-xl bg-accent px-4 py-2.5 text-sm font-medium text-white disabled:opacity-60 dark:text-black">
          {busy ? t("Generating…") : mode === "publish" ? t("Create share page") : t("Download HTML")}
        </button>
      </div>
    </div>
  );
}
