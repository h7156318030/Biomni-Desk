"use client";

import { useCallback, useEffect, useState } from "react";
import { chatgptLogin, chatgptLogout, chatgptStatus, type ChatGPTStatus } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

/** Sign in to ChatGPT from the page: shows the code to type at OpenAI's device page, then waits for the result. */
export function ChatGPTLogin() {
  const { t } = useI18n();
  const [st, setSt] = useState<ChatGPTStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setSt(await chatgptStatus());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(refresh, 0);
    return () => clearTimeout(timer);
  }, [refresh]);

  // While a code is waiting to be entered, look for the result every few seconds.
  const waiting = !!st?.pending;
  useEffect(() => {
    if (!waiting) return;
    const timer = setInterval(refresh, 3000);
    return () => clearInterval(timer);
  }, [waiting, refresh]);

  const act = async (fn: () => Promise<ChatGPTStatus>) => {
    setBusy(true);
    setError(null);
    try {
      setSt(await fn());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  if (!st) return error ? <p className="text-xs text-warn">{error}</p> : null;
  return (
    <div className="rounded-lg border border-line p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-medium">{t("ChatGPT sign-in")}</h3>
          <p className="text-xs text-soft">
            {st.logged_in
              ? t("Signed in: gpt-6-luna goes directly through the ChatGPT backend, used only as a model, and does not load Codex's own plug-ins or tools.")
              : t("Not signed in. Sign in once to use your ChatGPT subscription directly, without any separate command-line tool.")}
          </p>
        </div>
        {st.logged_in ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => act(chatgptLogout)}
            className="rounded-md border border-line px-2.5 py-1 text-xs hover:border-warn hover:text-warn disabled:opacity-50"
          >
            {t("Sign out")}
          </button>
        ) : (
          <button
            type="button"
            disabled={busy || waiting}
            onClick={() => act(chatgptLogin)}
            className="rounded-md bg-accent px-2.5 py-1 text-xs text-white disabled:opacity-50 dark:text-black"
          >
            {waiting ? t("Waiting for sign-in…") : t("Sign in to ChatGPT")}
          </button>
        )}
      </div>
      {st.pending && (
        <div className="mt-3 rounded-md bg-accent-soft p-3 text-sm">
          <p>
            {t("1. Open")}{" "}
            <a href={st.pending.verification_url} target="_blank" rel="noreferrer" className="text-accent underline">
              {st.pending.verification_url}
            </a>{" "}
            {t("in your browser")}
          </p>
          <p className="mt-1">
            {t("2. Enter the code")}{" "}
            <kbd className="rounded border border-line bg-card px-2 py-0.5 font-mono text-base tracking-wider">{st.pending.user_code}</kbd>
            {t(", then sign in and confirm with your ChatGPT account.")}
          </p>
          <p className="mt-1 text-xs text-soft">
            {t("This page checks the result automatically; the code is valid for 15 minutes. Sign-in credentials are stored only in the ui_data folder on this computer.")}
          </p>
        </div>
      )}
      {(error || st.error) && <p className="mt-2 text-xs text-warn">{error ?? st.error}</p>}
    </div>
  );
}
