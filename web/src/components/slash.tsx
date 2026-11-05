"use client";

import { useI18n } from "@/lib/i18n";

export type SlashCommand = { id: "plan" | "new" | "review" | "help" | "layout"; label: string; hint: string; aliases: string[] };

// Labels are the English command words; the Chinese aliases still match when typed.
export const COMMANDS: SlashCommand[] = [
  { id: "plan", label: "/plan", hint: "Toggle: confirm the plan with me before it runs", aliases: ["计划"] },
  { id: "new", label: "/new", hint: "Start a new conversation", aliases: ["新任务"] },
  { id: "review", label: "/review", hint: "Ask the model to check the last answer", aliases: ["审查"] },
  { id: "layout", label: "/layout", hint: "Show or hide the right column", aliases: ["布局"] },
  { id: "help", label: "/shortcuts", hint: "View keyboard shortcuts", aliases: ["快捷键"] },
];

/** The text after a leading "/" when the whole input is still a single slash word, otherwise null. */
export function slashQuery(text: string): string | null {
  const m = /^\/([^\s/]*)$/.exec(text);
  return m ? m[1] : null;
}

export function filterCommands(query: string): SlashCommand[] {
  const q = query.trim().toLowerCase();
  return COMMANDS.filter((c) => !q || c.label.slice(1).toLowerCase().includes(q) || c.id.startsWith(q) || c.aliases.some((a) => a.includes(q)));
}

export function SlashMenu({
  items,
  index,
  onPick,
}: {
  items: SlashCommand[];
  index: number;
  onPick: (c: SlashCommand) => void;
}) {
  const { t } = useI18n();
  if (!items.length) return null;
  return (
    <ul role="listbox" aria-label={t("Commands")} className="absolute bottom-full left-0 z-20 mb-2 w-72 overflow-hidden rounded-xl border border-line bg-panel py-1 shadow-lg">
      {items.map((c, i) => (
        <li key={c.id} role="option" aria-selected={i === index}>
          <button
            type="button"
            onMouseDown={(e) => {
              e.preventDefault();
              onPick(c);
            }}
            className={`flex w-full items-baseline justify-between gap-3 px-3 py-1.5 text-left text-sm ${i === index ? "bg-accent-soft" : "hover:bg-card"}`}
          >
            <span className="font-medium">{c.label}</span>
            <span className="truncate text-xs text-soft">{t(c.hint)}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}

/** Previous questions, newest first, without repeats. */
export function promptHistory(prompts: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (let i = prompts.length - 1; i >= 0; i--) {
    const p = prompts[i].trim();
    if (p && !seen.has(p)) {
      seen.add(p);
      out.push(p);
    }
  }
  return out;
}
