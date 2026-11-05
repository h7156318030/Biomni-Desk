"use client";

import { useEffect, useRef, useState } from "react";
import { listUploads, type Upload } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

/** The ＋ in the composer: bring files in. Skills and resources have their own visible buttons. */
export function AttachMenu({
  onFiles,
  onPickUploaded,
  disabled,
}: {
  onFiles: (files: FileList) => void;
  onPickUploaded: (f: Upload) => void;
  disabled?: boolean;
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [view, setView] = useState<"main" | "uploads">("main");
  const [uploads, setUploads] = useState<Upload[] | null>(null);
  const box = useRef<HTMLDivElement>(null);
  const filesInput = useRef<HTMLInputElement>(null);
  const folderInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const toggle = () => {
    setView("main");
    setOpen((o) => !o);
  };
  const close = () => setOpen(false);
  const item = "flex w-full items-center justify-between gap-2 px-3 py-1.5 text-left text-sm hover:bg-accent-soft disabled:opacity-40 disabled:hover:bg-transparent";

  return (
    <div ref={box} className="relative">
      <button
        type="button"
        title={t("Add files, cite skills and resources")}
        aria-label={t("Add")}
        aria-haspopup="menu"
        aria-expanded={open}
        disabled={disabled}
        onClick={toggle}
        className="grid h-8 w-8 place-items-center rounded-full border border-line text-lg leading-none text-soft hover:border-accent disabled:opacity-40"
      >
        ＋
      </button>
      <input ref={filesInput} type="file" multiple className="hidden" onChange={(e) => e.target.files && (onFiles(e.target.files), (e.target.value = ""))} />
      <input
        ref={(el) => {
          folderInput.current = el;
          // Not in React's typings: lets the picker choose a whole folder.
          el?.setAttribute("webkitdirectory", "");
        }}
        type="file"
        className="hidden"
        onChange={(e) => e.target.files && (onFiles(e.target.files), (e.target.value = ""))}
      />
      {open && (
        <div role="menu" className="absolute bottom-full left-0 z-30 mb-2 w-64 overflow-hidden rounded-xl border border-line bg-panel py-1 shadow-xl">
          {view === "main" ? (
            <>
              <button type="button" role="menuitem" className={item} onClick={() => (close(), filesInput.current?.click())}>
                {t("Upload files")}
              </button>
              <button type="button" role="menuitem" className={item} onClick={() => (close(), folderInput.current?.click())}>
                {t("Upload a folder")}
              </button>
              <button
                type="button"
                role="menuitem"
                className={item}
                onClick={async () => {
                  setView("uploads");
                  setUploads(null);
                  try {
                    setUploads(await listUploads());
                  } catch {
                    setUploads([]);
                  }
                }}
              >
                {t("Choose from uploaded files")} <span className="text-soft">›</span>
              </button>
            </>
          ) : (
            <>
              <button type="button" className="block w-full px-3 py-1.5 text-left text-xs text-soft hover:text-accent" onClick={() => setView("main")}>
                {t("‹ Back")}
              </button>
              <ul className="max-h-60 overflow-y-auto">
                {uploads === null && <li className="px-3 py-1.5 text-xs text-soft">{t("Loading…")}</li>}
                {uploads?.length === 0 && <li className="px-3 py-1.5 text-xs text-soft">{t("No files in the drive yet.")}</li>}
                {uploads?.map((f) => (
                  <li key={f.path}>
                    <button type="button" role="menuitem" className={item} onClick={() => (close(), onPickUploaded(f))} title={f.name}>
                      <span className="truncate">{f.name}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </div>
  );
}
