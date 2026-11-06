"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getNotebook, type Notebook } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

/** A session read as a notebook: each question, code step (with its output), tool call and answer, in the order they happened. */
export default function NotebookPage() {
  const { t } = useI18n();
  const [id, setId] = useState<string | null>(null);
  const [nb, setNb] = useState<Notebook | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const cid = new URLSearchParams(window.location.search).get("c");
    if (!cid) {
      setError(t("Open a session first, then choose Notebook."));
      return;
    }
    setId(cid);
    getNotebook(cid)
      .then(setNb)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (error) return <div className="p-8 text-sm text-warn">{error}</div>;
  if (!nb) return <div className="p-8 text-sm text-soft">{t("Loading…")}</div>;

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-4xl px-6 py-8">
        <div className="flex items-center justify-between gap-3">
          <Link href={id ? `/?open=${encodeURIComponent(id)}` : "/"} className="text-xs text-soft hover:text-accent">
            ← {t("Back to the session")}
          </Link>
          <span className="text-xs text-soft">
            {t("Python {version} on {platform}", { version: nb.environment.python, platform: nb.environment.platform })}
          </span>
        </div>
        <p className="mt-4 text-[11px] tracking-wider text-soft">{t("Notebook")}</p>
        <h1 className="font-serif text-2xl font-semibold">{nb.title}</h1>

        {nb.cells.length === 0 ? (
          <p className="mt-6 text-sm text-soft">{t("This session has no steps yet.")}</p>
        ) : (
          <ol className="mt-6 space-y-4">
            {nb.cells.map((c, i) => (
              <li key={i}>
                {c.kind === "question" && (
                  <div className="rounded-xl bg-accent-soft px-4 py-3 text-sm">
                    <span className="mr-2 text-xs text-soft">{t("Question")}</span>
                    <span className="whitespace-pre-wrap">{c.text}</span>
                  </div>
                )}
                {c.kind === "code" && (
                  <div className="overflow-hidden rounded-xl border border-line">
                    <div className="flex items-center justify-between bg-codebg px-3 py-1 text-xs text-soft">
                      <span>[{i + 1}] {c.language || "code"}</span>
                      {c.elapsed != null && <span>{c.elapsed}s</span>}
                    </div>
                    <pre className="overflow-x-auto whitespace-pre-wrap px-3 py-2 text-xs">{c.code}</pre>
                    {c.output && <pre className="overflow-x-auto whitespace-pre-wrap border-t border-line bg-card px-3 py-2 text-xs text-soft">{c.output}</pre>}
                    {c.files.length > 0 && (
                      <ul className="border-t border-line px-3 py-1 text-xs">
                        {c.files.map((f) => (
                          <li key={f} className="truncate text-accent">
                            {f.split(/[\\/]/).pop()}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
                {c.kind === "tool" && (
                  <div className="rounded-lg border border-line px-3 py-2 text-xs text-soft">
                    <span className="font-mono">{c.tool}</span>
                    {c.query && <span> · {c.query}</span>}
                  </div>
                )}
                {c.kind === "answer" && <div className="whitespace-pre-wrap rounded-xl border border-line bg-card px-4 py-3 text-sm">{c.text}</div>}
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}
