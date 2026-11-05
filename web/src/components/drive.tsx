"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { deleteUpload, listUploads, uploadFile, type Upload } from "@/lib/api";
import { formatSize } from "@/components/results-panel";
import { PublishedList } from "@/components/published-list";
import { tr, useI18n } from "@/lib/i18n";

/** "Drive": files the user uploaded for the agent to work on; click one to cite it in the question. */
export function Drive({ onPick, version = 0, publishedVersion = 0 }: { onPick: (file: Upload) => void; version?: number; publishedVersion?: number }) {
  const { t } = useI18n();
  const [tab, setTab] = useState<"files" | "published">("files");
  const [files, setFiles] = useState<Upload[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(true);
  const input = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    try {
      setFiles(await listUploads());
    } catch {}
  }, []);

  useEffect(() => {
    const timer = setTimeout(refresh, 0);
    return () => clearTimeout(timer);
  }, [refresh, version]);

  // A result was just published: show the tab it landed in.
  useEffect(() => {
    if (!publishedVersion) return;
    const timer = setTimeout(() => {
      setTab("published");
      setOpen(true);
    }, 0);
    return () => clearTimeout(timer);
  }, [publishedVersion]);

  const onFiles = async (list: FileList | null) => {
    if (!list?.length) return;
    setBusy(true);
    setError(null);
    for (const f of Array.from(list)) {
      try {
        await uploadFile(f);
      } catch (e) {
        setError(tr("{name}: {error}", { name: f.name, error: e instanceof Error ? e.message : String(e) }));
      }
    }
    setBusy(false);
    if (input.current) input.current.value = "";
    refresh();
  };

  return (
    <section className="mt-3 border-t border-line pt-3">
      <div className="flex items-center justify-between">
        <button type="button" onClick={() => setOpen((o) => !o)} className="flex items-center gap-1 text-sm text-soft" aria-expanded={open}>
          <span className={`text-xs transition-transform ${open ? "" : "-rotate-90"}`}>▾</span> {t("Drive")}
        </button>
        {tab === "files" && (
          <button type="button" onClick={() => input.current?.click()} disabled={busy} className="text-sm text-soft hover:text-accent disabled:opacity-50">
            {busy ? t("Uploading…") : t("＋ Upload")}
          </button>
        )}
        <input ref={input} type="file" multiple className="hidden" onChange={(e) => onFiles(e.target.files)} />
      </div>
      {error && <p className="mt-1 text-xs text-warn">{error}</p>}
      {open && (
        <div className="mt-1.5 flex gap-1.5 text-xs" role="tablist" aria-label={t("Drive")}>
          {(
            [
              ["files", "My files"],
              ["published", "Published results"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={tab === id}
              onClick={() => setTab(id)}
              className={`rounded-full border px-2.5 py-0.5 ${tab === id ? "border-accent bg-accent-soft text-accent" : "border-line text-soft hover:border-accent"}`}
            >
              {t(label)}
            </button>
          ))}
        </div>
      )}
      {open && tab === "published" && <PublishedList version={publishedVersion} />}
      {open && tab === "files" && (
        <ul className="mt-1.5 max-h-40 space-y-0.5 overflow-y-auto">
          {files.map((f) => (
            <li key={f.path} className="group flex items-center gap-1.5 rounded-md px-1.5 py-1 text-sm hover:bg-card">
              <button type="button" onClick={() => onPick(f)} className="min-w-0 flex-1 truncate text-left" title={t("Click to cite this file in your question")}>
                {f.name}
              </button>
              <span className="shrink-0 text-xs text-soft group-hover:hidden">{formatSize(f.size)}</span>
              <button
                type="button"
                title={t("Delete")}
                onClick={async () => {
                  if (!window.confirm(tr("Delete “{name}”?", { name: f.name }))) return;
                  await deleteUpload(f.name);
                  refresh();
                }}
                className="hidden text-xs text-warn group-hover:block"
              >
                ✕
              </button>
            </li>
          ))}
          {files.length === 0 && <li className="px-1.5 text-xs text-soft">{t("No files yet. After uploading, cite them with @ or by clicking.")}</li>}
        </ul>
      )}
    </section>
  );
}
