"use client";

import { useI18n } from "@/lib/i18n";

/** A question only the user can answer: the options as buttons; a click sends the pick as the next message. */
export function AskChoices({ options, onPick }: { options: string[]; onPick: (q: string) => void }) {
  const { t } = useI18n();
  return (
    <section className="rounded-xl border border-accent bg-card" aria-label={t("You need to choose")}>
      <p className="px-4 pt-2.5 text-sm font-medium">{t("You need to choose")}</p>
      <ul className="mt-1 border-t border-line">
        {options.map((o) => (
          <li key={o} className="border-b border-line last:border-b-0">
            <button type="button" onClick={() => onPick(o)} className="flex w-full gap-2 px-4 py-2 text-left text-sm hover:bg-panel">
              <span className="text-accent">→</span>
              <span>{o}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
