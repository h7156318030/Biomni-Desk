"use client";

import { useState } from "react";
import { downloadUrl, openOnHost } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

/** What can be done with a result file: open it with the program this computer uses for that type, show it in its folder, or download it. */
export function FileActions({ path, compact = false }: { path: string; compact?: boolean }) {
  const { t } = useI18n();
  const [error, setError] = useState("");
  const run = async (action: "open" | "folder") => {
    setError("");
    try {
      await openOnHost(path, action);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };
  const btn = "text-xs text-accent underline-offset-2 hover:underline";
  return (
    <span className={`inline-flex flex-wrap items-center ${compact ? "gap-2" : "gap-3"}`}>
      <button
        type="button"
        className={btn}
        title={t("Open with this computer's default program (PowerPoint for slides, Excel for tables…)")}
        onClick={() => run("open")}
      >
        {t("Open")}
      </button>
      <button type="button" className={btn} title={t("Show this file in its folder")} onClick={() => run("folder")}>
        {t("Show in folder")}
      </button>
      <a className={btn} href={downloadUrl(path)} title={t("Download a copy")}>
        {t("Download")}
      </a>
      {error && <span className="text-xs text-warn">{error}</span>}
    </span>
  );
}
