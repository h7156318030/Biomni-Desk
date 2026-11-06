"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useI18n } from "@/lib/i18n";

export const SHORTCUTS_EVENT = "biomni:shortcuts";

const ICON = {
  project: <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />,
  skills: <path d="M13 3 5 14h6l-1 7 8-11h-6z" />,
  pipelines: (
    <>
      <circle cx="6" cy="6" r="2.2" />
      <circle cx="18" cy="18" r="2.2" />
      <path d="M8.2 6H14a3 3 0 0 1 3 3v1m-9.8 4H10a3 3 0 0 0 3 3h2.8" />
    </>
  ),
  schedules: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7.5V12l3 2" />
    </>
  ),
  resources: (
    <>
      <ellipse cx="12" cy="5" rx="8" ry="3" />
      <path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6" />
    </>
  ),
  settings: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M19 12a7 7 0 0 0-.1-1.2l2-1.5-2-3.4-2.3.9a7 7 0 0 0-2-1.2L14.2 3h-4l-.4 2.6a7 7 0 0 0-2 1.2l-2.3-.9-2 3.4 2 1.5A7 7 0 0 0 5 12c0 .4 0 .8.1 1.2l-2 1.5 2 3.4 2.3-.9a7 7 0 0 0 2 1.2l.4 2.6h4l.4-2.6a7 7 0 0 0 2-1.2l2.3.9 2-3.4-2-1.5c.1-.4.1-.8.1-1.2z" />
    </>
  ),
  language: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3z" />
    </>
  ),
} as const;

function Icon({ name }: { name: keyof typeof ICON }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {ICON[name]}
    </svg>
  );
}

// Labels are English source strings; the language provider translates them.
const NAV: { href: string; label: string; icon: keyof typeof ICON; match: (p: string) => boolean }[] = [
  { href: "/projects", label: "Projects", icon: "project", match: (p) => p.startsWith("/projects") || p.startsWith("/project") },
  { href: "/skills", label: "Skills", icon: "skills", match: (p) => p.startsWith("/skills") },
  { href: "/resources", label: "Resources", icon: "resources", match: (p) => p.startsWith("/resources") },
  { href: "/pipelines", label: "Pipelines", icon: "pipelines", match: (p) => p.startsWith("/pipelines") },
  { href: "/schedules", label: "Schedules", icon: "schedules", match: (p) => p.startsWith("/schedules") },
];

function RailItem({ active, label, children }: { active: boolean; label: string; children: React.ReactNode }) {
  return (
    <span className="flex w-full flex-col items-center gap-1 py-1.5 text-[11px]">
      <span className={`grid h-9 w-9 place-items-center rounded-full transition-colors ${active ? "bg-accent-soft text-accent" : "text-soft group-hover:bg-card group-hover:text-ink"}`}>{children}</span>
      <span className={active ? "text-ink" : "text-soft"}>{label}</span>
    </span>
  );
}

/** The narrow icon bar on the far left: the main pages, the language switch and settings. Hidden on phones (the pages have their own links). */
export function Rail() {
  const path = usePathname() ?? "/";
  const { t, lang, setLang } = useI18n();
  const nextLang = lang === "en" ? "zh" : "en";
  const nextLangName = lang === "en" ? "中文" : "English";

  return (
    <nav aria-label={t("Main navigation")} className="hidden w-14 shrink-0 flex-col items-center border-r border-line bg-panel py-3 lg:flex">
      <Link href="/" aria-label={t("Biomni-Desk home")} className="mb-3 text-accent">
        <svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true">
          <circle cx="14" cy="14" r="12.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
          <path d="M14 5.5c-4.2 2.6-5.6 7.4-3 11.2 1.6 2.3 4.6 3.4 7.2 2.2M14 5.5c3.4 1.6 5 5.2 3.8 8.4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
          <circle cx="14" cy="14" r="1.9" fill="currentColor" />
        </svg>
      </Link>
      {NAV.map((n) => (
        <Link key={n.href} href={n.href} aria-current={n.match(path) ? "page" : undefined} className="group w-full">
          <RailItem active={n.match(path)} label={t(n.label)}>
            <Icon name={n.icon} />
          </RailItem>
        </Link>
      ))}

      <div className="mt-auto" />

      <button type="button" onClick={() => setLang(nextLang)} aria-label={t("Language")} title={t("Language")} className="group mt-1 w-full">
        <RailItem active={false} label={nextLangName}>
          <Icon name="language" />
        </RailItem>
      </button>

      <Link href="/settings" aria-current={path.startsWith("/settings") ? "page" : undefined} className="group mt-1 w-full">
        <RailItem active={path.startsWith("/settings")} label={t("Settings")}>
          <Icon name="settings" />
        </RailItem>
      </Link>
    </nav>
  );
}
