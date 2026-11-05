"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { getNotes, putNotes } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

type Save = "idle" | "saving" | "saved" | "error";

/** Free-form notes for the open task, saved on the server shortly after you stop typing. */
export function NotesPanel({ conversationId }: { conversationId: string | null }) {
  const { t } = useI18n();
  const [state, setState] = useState<{ id: string | null; text: string; loaded: boolean }>({ id: null, text: "", loaded: false });
  const [save, setSave] = useState<Save>("idle");
  const [preview, setPreview] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const id = conversationId;

  useEffect(() => {
    let alive = true;
    if (!id) {
      const timeoutId = setTimeout(() => setState({ id: null, text: "", loaded: true }), 0);
      return () => clearTimeout(timeoutId);
    }
    getNotes(id)
      .then((r) => alive && setState({ id, text: r.text, loaded: true }))
      .catch(() => alive && setState({ id, text: "", loaded: true }));
    return () => {
      alive = false;
    };
  }, [id]);

  const change = (text: string) => {
    setState((s) => ({ ...s, text }));
    if (!id) return;
    setSave("saving");
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      try {
        await putNotes(id, text);
        setSave("saved");
      } catch {
        setSave("error");
      }
    }, 800);
  };

  useEffect(() => () => void (timer.current && clearTimeout(timer.current)), []);

  if (!id) return <p className="text-sm text-soft">{t("Once you start a task, you can take notes here; they are saved with the task.")}</p>;
  const text = state.id === id ? state.text : "";
  return (
    <div>
      <div className="mb-1.5 flex items-center gap-1 text-xs" role="tablist" aria-label={t("Note view")}>
        {(
          [
            [false, "Edit"],
            [true, "Preview"],
          ] as const
        ).map(([p, label]) => (
          <button
            key={label}
            type="button"
            role="tab"
            aria-selected={preview === p}
            onClick={() => setPreview(p)}
            className={`rounded-full border px-2.5 py-0.5 ${preview === p ? "border-accent bg-accent-soft text-accent" : "border-line text-soft hover:border-accent"}`}
          >
            {t(label)}
          </button>
        ))}
        <span className="ml-auto text-soft">{t("Markdown supported")}</span>
      </div>
      {preview ? (
        text.trim() ? (
          <div className="md min-h-[8rem] rounded-md border border-line bg-card px-3 py-2 text-sm">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
          </div>
        ) : (
          <p className="rounded-md border border-dashed border-line px-3 py-6 text-center text-sm text-soft">
            {t("No notes yet. Switch to “Edit” to write some.")}
          </p>
        )
      ) : (
        <textarea
          value={text}
          disabled={!state.loaded || state.id !== id}
          onChange={(e) => change(e.target.value)}
          rows={6}
          maxLength={20000}
          placeholder={t("Note ideas, points to check, conclusions… (Markdown supported)")}
          aria-label={t("Task notes")}
          className="w-full resize-y rounded-md border border-line bg-card px-2.5 py-2 text-sm outline-none focus:border-accent"
        />
      )}
      <p className="mt-1 text-xs text-soft">
        {save === "saving" ? (
          t("Saving…")
        ) : save === "saved" ? (
          t("Saved")
        ) : save === "error" ? (
          <span className="text-warn">{t("Save failed; check the backend")}</span>
        ) : (
          t("Autosaves")
        )}
      </p>
    </div>
  );
}
