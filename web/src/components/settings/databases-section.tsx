"use client";

import { useEffect, useState } from "react";
import { getConnectors, listGrants, listProjects, revokeGrant, setConnector, type Connector, type Grant, type Project } from "@/lib/api";
import { Card, Toggle } from "@/components/settings/ui";
import { useI18n } from "@/lib/i18n";

/** Which research databases the agent may query, and the standing permissions it was given. Both apply from the next task on; no restart. */
export function DatabasesSection() {
  const { t, lang } = useI18n();
  const [connectors, setConnectors] = useState<Connector[] | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [grants, setGrants] = useState<Grant[] | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const listSep = lang === "zh" ? "、" : ", ";

  useEffect(() => {
    getConnectors()
      .then((r) => setConnectors(r.connectors))
      .catch(() => setConnectors([]));
    listProjects()
      .then(setProjects)
      .catch(() => setProjects([]));
    listGrants()
      .then((r) => setGrants(r.grants))
      .catch(() => setGrants([]));
  }, []);

  const flip = async (id: string, on: boolean) => {
    try {
      const r = await setConnector(id, on);
      setConnectors(r.connectors);
      setMsg(null);
    } catch {
      setMsg(t("Could not save. Please try again."));
    }
  };

  const unlock = async (g: Grant) => {
    try {
      const r = await revokeGrant(g);
      setGrants(r.grants);
      setMsg(null);
    } catch {
      setMsg(t("Could not save. Please try again."));
    }
  };

  const grantScope = (g: Grant) =>
    g.scope === "global" ? t("Everywhere") : g.scope === "project" ? `${t("Project")}: ${projects.find((p) => p.id === g.key)?.name ?? g.key}` : t("This conversation");

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
        title={t("Standing permissions")}
        hint={t("Database connectors the agent may query without asking again. Revoke one here and the agent asks next time.")}
      >
        {grants === null ? (
          <p className="text-sm text-soft">{t("Loading…")}</p>
        ) : grants.length === 0 ? (
          <p className="text-sm text-soft">{t("No standing permissions. The agent asks you the first time it queries a database.")}</p>
        ) : (
          <ul className="space-y-2">
            {grants.map((g) => (
              <li key={`${g.scope}:${g.key}:${g.tool}`} className="flex items-center justify-between gap-3 rounded-md border border-line px-3 py-2">
                <span className="text-sm">
                  {g.tool} <span className="text-xs text-soft">· {grantScope(g)}</span>
                </span>
                <button type="button" onClick={() => unlock(g)} className="shrink-0 text-xs text-soft hover:text-warn">
                  {t("Revoke")}
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
