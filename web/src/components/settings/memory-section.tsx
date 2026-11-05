"use client";

import { useCallback, useEffect, useState } from "react";
import { deleteMemoryNote, getConnectors, getMemoryNotes, setConnector, type Connector, type MemoryNote } from "@/lib/api";
import { Card, Toggle } from "@/components/settings/ui";
import { useI18n } from "@/lib/i18n";

/** Which research databases the agent may query, and what the user asked it to remember. Both apply from the next task on; no restart. */
export function MemorySection() {
  const { t, lang } = useI18n();
  const [connectors, setConnectors] = useState<Connector[] | null>(null);
  const [notes, setNotes] = useState<MemoryNote[] | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback(() => {
    getConnectors()
      .then((r) => setConnectors(r.connectors))
      .catch(() => setConnectors([]));
    getMemoryNotes()
      .then((r) => setNotes(r.items))
      .catch(() => setNotes([]));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const flip = async (id: string, on: boolean) => {
    try {
      const r = await setConnector(id, on);
      setConnectors(r.connectors);
      setMsg(null);
    } catch {
      setMsg(t("Could not save. Please try again."));
    }
  };

  const forget = async (id: string) => {
    try {
      const r = await deleteMemoryNote(id);
      setNotes(r.items);
      setMsg(null);
    } catch {
      setMsg(t("Could not delete. Please try again."));
    }
  };

  const listSep = lang === "zh" ? "、" : ", ";

  return (
    <div className="space-y-6">
      <Card
        title={t("Database connectors")}
        hint={t("A database that is switched off is not queried and does not appear in the agent's tool list. Changes take effect from the next task; no restart needed.")}
      >
        {connectors === null ? (
          <p className="text-sm text-soft">{t("Loading…")}</p>
        ) : (
          connectors.map((c) => <Toggle key={c.id} checked={c.enabled} onChange={(v) => flip(c.id, v)} label={t(c.title)} hint={c.tools.join(listSep)} />)
        )}
      </Card>

      <Card
        title={t("Things to remember")}
        hint={t("Send a separate message in a conversation starting with “remember: …”; later tasks will take it into account. You can view and delete them here.")}
      >
        {notes === null ? (
          <p className="text-sm text-soft">{t("Loading…")}</p>
        ) : notes.length === 0 ? (
          <p className="text-sm text-soft">{t("Nothing remembered yet.")}</p>
        ) : (
          <ul className="space-y-2">
            {notes.map((n) => (
              <li key={n.id} className="flex items-start justify-between gap-3 rounded-md border border-line px-3 py-2">
                <span className="text-sm">{n.text}</span>
                <button type="button" onClick={() => forget(n.id)} className="shrink-0 text-xs text-soft hover:text-warn">
                  {t("Delete")}
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {msg && <p className="text-sm text-warn">{msg}</p>}
    </div>
  );
}
