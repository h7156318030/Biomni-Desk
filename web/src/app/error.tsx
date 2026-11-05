"use client";

import { useI18n } from "@/lib/i18n";

export default function ErrorPage({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  const { t } = useI18n();
  return (
    <div className="flex h-full items-center justify-center p-6">
      <div className="max-w-lg space-y-3 rounded-xl border border-warn/50 bg-card p-6">
        <h1 className="font-serif text-xl font-semibold text-warn">{t("Something went wrong on this page")}</h1>
        <p className="text-sm text-soft">
          {t("The interface hit an unexpected error. Try again; if it keeps happening, send the information below to the developer.")}
        </p>
        <pre className="max-h-48 overflow-auto rounded-md bg-codebg p-3 text-xs whitespace-pre-wrap">
          {error.message}
          {error.digest ? `\n(digest: ${error.digest})` : ""}
        </pre>
        <button type="button" onClick={reset} className="rounded-lg bg-accent px-4 py-2 text-sm text-white dark:text-black">
          {t("Try again")}
        </button>
      </div>
    </div>
  );
}
