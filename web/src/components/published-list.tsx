"use client";

import { useCallback, useEffect, useState } from "react";
import { deletePublished, listPublished, publishedUrl, type Published } from "@/lib/api";
import { relativeTime } from "@/lib/time";
import { tr, useI18n } from "@/lib/i18n";

export function PublishedList({ version }: { version: number }) {
  const { t } = useI18n();
  const [rows, setRows] = useState<Published[] | null>(null);

  const refresh = useCallback(async () => {
    try {
      setRows(await listPublished());
    } catch {
      setRows([]);
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(refresh, 0);
    return () => clearTimeout(timer);
  }, [refresh, version]);

  if (rows === null) return <p className="px-1.5 text-xs text-soft">{t("Loading…")}</p>;
  if (!rows.length)
    return (
      <p className="px-1.5 text-xs text-soft">{t("No published results yet. On a task page, click “Share” → “Publish to the drive”.")}</p>
    );
  return (
    <ul className="mt-1.5 max-h-40 space-y-0.5 overflow-y-auto">
      {rows.map((p) => (
        <li key={p.id} className="group flex items-center gap-1.5 rounded-md px-1.5 py-1 text-sm hover:bg-card">
          <a href={publishedUrl(p.id)} target="_blank" rel="noreferrer" className="min-w-0 flex-1 truncate" title={p.title}>
            {p.title}
          </a>
          <span className="shrink-0 text-xs text-soft group-hover:hidden">{relativeTime(p.created)}</span>
          <button
            type="button"
            title={t("Unpublish")}
            onClick={async () => {
              if (!window.confirm(tr("Unpublish “{title}”?", { title: p.title }))) return;
              await deletePublished(p.id);
              refresh();
            }}
            className="hidden text-xs text-warn group-hover:block"
          >
            ✕
          </button>
        </li>
      ))}
    </ul>
  );
}
