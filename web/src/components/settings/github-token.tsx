"use client";

import { useEffect, useState } from "react";
import { githubTokenState, setGithubToken } from "@/lib/api";
import { Card, inputCls } from "@/components/settings/ui";
import { useI18n } from "@/lib/i18n";

/** The GitHub token used to import skills from private repositories and to check them for updates. Kept on this computer only. */
export function GitHubTokenCard() {
  const { t } = useI18n();
  const [isSet, setIsSet] = useState<boolean | null>(null);
  const [draft, setDraft] = useState("");
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    githubTokenState()
      .then((r) => setIsSet(r.set))
      .catch(() => setIsSet(false));
  }, []);

  const save = async (token: string | null) => {
    setMsg(null);
    try {
      const r = await setGithubToken(token);
      setIsSet(r.set);
      setDraft("");
      setMsg(r.set ? t("Saved on this computer. The token is not shown again.") : t("Token removed."));
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <Card
      title={t("GitHub token for skills")}
      hint={t("Needed only for private repositories, and to check imported skills for updates. Stored on this computer; it is never sent to the page again.")}
    >
      <p className="text-sm text-soft">{isSet === null ? t("Loading…") : isSet ? t("A token is set.") : t("No token set.")}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        <input
          type="password"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={t("Paste a GitHub token (read access to the repository)")}
          aria-label={t("GitHub token")}
          className={`${inputCls} min-w-0 flex-1`}
        />
        <button type="button" onClick={() => save(draft)} disabled={!draft.trim()} className="rounded-md bg-accent px-3 py-1.5 text-sm text-white disabled:opacity-50">
          {t("Save token")}
        </button>
        {isSet && (
          <button type="button" onClick={() => save(null)} className="rounded-md border border-line px-3 py-1.5 text-sm hover:border-warn">
            {t("Remove")}
          </button>
        )}
      </div>
      {msg && <p className="mt-2 text-xs text-soft">{msg}</p>}
    </Card>
  );
}
