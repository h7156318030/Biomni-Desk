"use client";

import { useState } from "react";
import { answerPermission } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export type PermissionRequest = { id: string; tool: string; title: string; choices: string[] };

const LABELS: Record<string, string> = {
  once: "Allow once",
  conversation: "Allow for this conversation",
  project: "Allow for this project",
  global: "Allow always",
  deny: "Don't allow",
};

/** Asks the user whether a database connector may be queried, and for how long. The task waits for the answer. */
export function PermissionCard({ taskId, request }: { taskId: string; request: PermissionRequest }) {
  const { t } = useI18n();
  const [sent, setSent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const answer = async (choice: string) => {
    setSent(choice);
    setError(null);
    try {
      await answerPermission(taskId, request.id, choice);
    } catch (e) {
      setSent(null);
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div className="rounded-xl border border-accent/50 bg-accent-soft p-4 text-sm" role="group" aria-label={t("Permission request")}>
      <p className="font-medium">
        {t("The agent wants to query the database “{name}”. Your data is sent to it.", { name: t(request.title) })}
      </p>
      <p className="mt-1 text-xs text-soft">{t("Choose how long this is allowed. Scopes you pick here can be revoked in Settings → Remember and database.")}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {request.choices.map((c) => (
          <button
            key={c}
            type="button"
            disabled={sent !== null}
            onClick={() => answer(c)}
            className={`rounded-full border px-3 py-1 text-xs ${c === "deny" ? "border-line text-soft hover:border-warn" : "border-accent text-accent hover:bg-card"} disabled:opacity-50`}
          >
            {t(LABELS[c] ?? c)}
          </button>
        ))}
      </div>
      {sent && <p className="mt-2 text-xs text-soft">{t("Answer sent.")}</p>}
      {error && <p className="mt-2 text-xs text-warn">{error}</p>}
    </div>
  );
}
