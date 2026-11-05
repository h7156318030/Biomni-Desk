"use client";

import { useEffect, useState } from "react";
import { useI18n } from "@/lib/i18n";

const TIPS = [
  "Click any citation in an answer to see the original source",
  "Use “Review” to have a second model check this answer",
  "Drag files into the input box to upload them to the drive and cite them automatically",
  "Double-click a task title in the sidebar to rename it",
  "Type / for commands: plan, new task, review, layout",
  "Press ↑ to bring back your last question",
  "Use @ to cite skills, tools, datasets and files; the agent will use them",
  "Browse every tool, dataset and package on the Resources page",
  "Share turns an answer into a standalone web page",
  "Click ☆ to save a question you use often, and reuse it from the home page",
];

/** One short hint above the composer, changing every few seconds. */
export function Tips() {
  const { t } = useI18n();
  const [i, setI] = useState(0);
  useEffect(() => {
    const first = setTimeout(() => setI(Math.floor(Math.random() * TIPS.length)), 0);
    const timer = setInterval(() => setI((n) => (n + 1) % TIPS.length), 9000);
    return () => {
      clearTimeout(first);
      clearInterval(timer);
    };
  }, []);
  return (
    <p className="mb-2 truncate text-center text-xs text-soft" aria-live="off">
      <span aria-hidden="true">✦ </span>
      {t(TIPS[i])}
    </p>
  );
}
