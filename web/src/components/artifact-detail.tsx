"use client";

import { useEffect, useState } from "react";
import {
  addComment,
  deleteComment,
  getProvenance,
  listComments,
  listVersions,
  restoreVersion,
  versionFileUrl,
  type Comment,
  type FileVersion,
  type Provenance,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { relativeTime } from "@/lib/time";

type Tab = "versions" | "provenance" | "comments";

/** One result file's history: its versions (restore an older one), how a version was made, and comments left on it. */
export function ArtifactDetail({ conversationId, path, name, onClose }: { conversationId: string; path: string; name: string; onClose: () => void }) {
  const { t } = useI18n();
  const [tab, setTab] = useState<Tab>("versions");
  const [versions, setVersions] = useState<FileVersion[] | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [prov, setProv] = useState<Provenance | null>(null);
  const [comments, setComments] = useState<Comment[] | null>(null);
  const [draft, setDraft] = useState("");
  const [quote, setQuote] = useState("");
  const [error, setError] = useState<string | null>(null);

  const loadVersions = () =>
    listVersions(conversationId, path)
      .then((r) => {
        setVersions(r.versions);
        setSelected((cur) => cur ?? r.versions[0]?.version ?? null);
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));

  useEffect(() => {
    loadVersions();
    listComments(conversationId)
      .then((r) => setComments(r.items.filter((c) => c.path === path)))
      .catch(() => setComments([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId, path]);

  useEffect(() => {
    if (tab !== "provenance" || selected == null) return;
    getProvenance(conversationId, path, selected)
      .then(setProv)
      .catch((e) => {
        setProv(null);
        setError(e instanceof Error ? e.message : String(e));
      });
  }, [tab, selected, conversationId, path]);

  const restore = async (v: FileVersion) => {
    setError(null);
    try {
      await restoreVersion(conversationId, path, v.version);
      await loadVersions();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const sendComment = async () => {
    if (!draft.trim()) return;
    setError(null);
    try {
      const r = await addComment(conversationId, path, draft.trim(), quote.trim());
      setComments(r.items.filter((c) => c.path === path));
      setDraft("");
      setQuote("");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const removeComment = async (id: string) => {
    try {
      const r = await deleteComment(conversationId, id);
      setComments(r.items.filter((c) => c.path === path));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const tabs: [Tab, string][] = [
    ["versions", "Versions"],
    ["provenance", "Provenance"],
    ["comments", "Comments"],
  ];

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/30 p-4" role="dialog" aria-label={t("Details of {name}", { name })} onClick={onClose}>
      <div className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-line bg-panel p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[11px] tracking-wider text-soft">{t("Result file")}</p>
            <h2 className="truncate font-serif text-xl font-semibold">{name}</h2>
          </div>
          <button type="button" onClick={onClose} className="text-soft hover:text-accent" aria-label={t("Close")}>
            ✕
          </button>
        </div>

        <div className="mt-3 flex gap-1 text-xs" role="tablist">
          {tabs.map(([id, label]) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={tab === id}
              onClick={() => setTab(id)}
              className={`rounded-full border px-3 py-1 ${tab === id ? "border-accent bg-accent-soft text-accent" : "border-line text-soft hover:border-accent"}`}
            >
              {t(label)}
            </button>
          ))}
        </div>

        {error && <p className="mt-3 text-sm text-warn">{error}</p>}

        {tab === "versions" && (
          <div className="mt-4">
            {versions === null ? (
              <p className="text-sm text-soft">{t("Loading…")}</p>
            ) : versions.length === 0 ? (
              <p className="text-sm text-soft">{t("No versions kept for this file yet.")}</p>
            ) : (
              <ul className="space-y-2">
                {versions.map((v, i) => (
                  <li key={v.version} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-line px-3 py-2 text-sm">
                    <span>
                      <span className="font-medium">v{v.version}</span>
                      {i === 0 && <span className="ml-2 text-xs text-accent">{t("latest")}</span>}
                      <span className="ml-2 text-xs text-soft">
                        {relativeTime(v.time)} · {v.reason || t("saved by a step")}
                      </span>
                    </span>
                    <span className="flex gap-3 text-xs">
                      <button
                        type="button"
                        onClick={() => {
                          setSelected(v.version);
                          setTab("provenance");
                        }}
                        className="text-accent hover:underline"
                      >
                        {t("Provenance")}
                      </button>
                      <a href={versionFileUrl(conversationId, v.sha256, name)} target="_blank" rel="noreferrer" className="text-accent hover:underline">
                        {t("Open")}
                      </a>
                      <a href={versionFileUrl(conversationId, v.sha256, name, true)} className="text-accent hover:underline">
                        {t("Download")}
                      </a>
                      {i !== 0 && (
                        <button type="button" onClick={() => restore(v)} className="text-accent hover:underline">
                          {t("Restore")}
                        </button>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {tab === "provenance" && (
          <div className="mt-4 space-y-4 text-sm">
            {versions && versions.length > 0 && (
              <label className="block text-xs">
                {t("Version")}
                <select value={selected ?? ""} onChange={(e) => setSelected(Number(e.target.value))} className="ml-2 rounded-md border border-line bg-card px-2 py-1">
                  {versions.map((v) => (
                    <option key={v.version} value={v.version}>
                      v{v.version}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {!prov ? (
              <p className="text-soft">{t("Loading…")}</p>
            ) : (
              <>
                <section>
                  <h3 className="font-medium">{t("Question")}</h3>
                  <p className="mt-1 whitespace-pre-wrap rounded-md bg-card p-2">{prov.messages.question || t("Not recorded.")}</p>
                </section>
                <section>
                  <h3 className="font-medium">{t("Answer")}</h3>
                  <p className="mt-1 line-clamp-6 whitespace-pre-wrap rounded-md bg-card p-2">{prov.messages.answer || t("Not recorded.")}</p>
                </section>
                <section>
                  <h3 className="font-medium">{t("Code steps")}</h3>
                  {prov.code.length === 0 ? (
                    <p className="mt-1 text-soft">{t("No code steps in this task.")}</p>
                  ) : (
                    prov.code.map((c, i) => (
                      <details key={i} className="mt-1 rounded-md bg-card p-2">
                        <summary className="cursor-pointer text-xs">{c.title || `${c.language} ${i + 1}`}</summary>
                        <pre className="mt-2 overflow-x-auto whitespace-pre-wrap text-xs">{c.code}</pre>
                      </details>
                    ))
                  )}
                </section>
                <section>
                  <h3 className="font-medium">{t("Execution log")}</h3>
                  {prov.execution_log.length === 0 ? (
                    <p className="mt-1 text-soft">{t("No tool calls were recorded for this task.")}</p>
                  ) : (
                    <ul className="mt-1 space-y-1 text-xs">
                      {prov.execution_log.map((r, i) => (
                        <li key={i} className="rounded-md bg-card px-2 py-1">
                          <span className="font-mono">{r.tool}</span> · {r.time}
                          {r.failed && <span className="text-warn"> · {t("failed")}</span>}
                          {r.summary && <span className="block truncate text-soft">{r.summary}</span>}
                        </li>
                      ))}
                    </ul>
                  )}
                </section>
                <section>
                  <h3 className="font-medium">{t("Environment")}</h3>
                  <p className="mt-1 text-xs text-soft">
                    Python {prov.environment.python} · {prov.environment.platform}
                    {prov.environment.model && ` · ${prov.environment.model}`}
                    {prov.environment.effort && ` · ${prov.environment.effort}`}
                  </p>
                </section>
                <section>
                  <h3 className="font-medium">{t("Review")}</h3>
                  <p className="mt-1 whitespace-pre-wrap text-xs text-soft">{prov.review || t("No review was made for this task.")}</p>
                </section>
              </>
            )}
          </div>
        )}

        {tab === "comments" && (
          <div className="mt-4 space-y-3 text-sm">
            <p className="text-xs text-soft">{t("Comments are sent with your next message in this session; the agent reads them with it.")}</p>
            {comments === null ? (
              <p className="text-soft">{t("Loading…")}</p>
            ) : comments.length === 0 ? (
              <p className="text-soft">{t("No comments on this file yet.")}</p>
            ) : (
              <ul className="space-y-2">
                {comments.map((c) => (
                  <li key={c.id} className="rounded-lg border border-line px-3 py-2">
                    {c.quote && <p className="mb-1 text-xs italic text-soft">“{c.quote}”</p>}
                    <p className="whitespace-pre-wrap">{c.text}</p>
                    <p className="mt-1 flex items-center justify-between text-xs text-soft">
                      <span>{c.sent_in_task ? t("Sent with a message") : t("Waiting for your next message")}</span>
                      {!c.sent_in_task && (
                        <button type="button" onClick={() => removeComment(c.id)} className="hover:text-warn">
                          {t("Delete")}
                        </button>
                      )}
                    </p>
                  </li>
                ))}
              </ul>
            )}
            <div className="space-y-2 rounded-lg border border-line p-3">
              <input value={quote} onChange={(e) => setQuote(e.target.value)} maxLength={500} placeholder={t("Quoted passage (optional)")} className="w-full rounded-md border border-line bg-card px-2 py-1.5 text-sm outline-none focus:border-accent" />
              <textarea value={draft} onChange={(e) => setDraft(e.target.value)} maxLength={1000} rows={3} placeholder={t("Your comment on this file")} className="w-full rounded-md border border-line bg-card px-2 py-1.5 text-sm outline-none focus:border-accent" />
              <div className="flex justify-end">
                <button type="button" onClick={sendComment} disabled={!draft.trim()} className="rounded-md bg-accent px-3 py-1.5 text-sm text-white disabled:opacity-50">
                  {t("Add comment")}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
