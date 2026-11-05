"use client";

import { useEffect, useState } from "react";
import { ModelsSection } from "@/components/settings/models-section";
import { AgentSection, ConnectionsSection, DataSection, UsageSection } from "@/components/settings/other-sections";
import { PersonalizationSection, ProfileSection } from "@/components/settings/prefs-sections";
import { MemorySection } from "@/components/settings/memory-section";
import { ProjectsSection } from "@/components/settings/projects-section";
import { useI18n } from "@/lib/i18n";

// Labels are English source strings; the page translates them when shown.
const GROUPS: { label: string; items: { id: string; label: string; icon: string }[] }[] = [
  { label: "Account", items: [{ id: "profile", label: "Profile", icon: "☺" }] },
  {
    label: "Workspace",
    items: [
      { id: "personalization", label: "Personalisation", icon: "✦" },
      { id: "projects", label: "Projects", icon: "▤" },
      { id: "models", label: "Models", icon: "◈" },
      { id: "agent", label: "Agent", icon: "⚙" },
      { id: "memory", label: "Remember and database", icon: "✎" },
      { id: "usage", label: "Usage", icon: "▥" },
    ],
  },
  {
    label: "Data",
    items: [
      { id: "connections", label: "Connections", icon: "⇄" },
      { id: "data", label: "Data and privacy", icon: "▣" },
    ],
  },
];
const IDS = GROUPS.flatMap((g) => g.items.map((i) => i.id));

function Section({ id }: { id: string }) {
  switch (id) {
    case "profile":
      return <ProfileSection />;
    case "personalization":
      return <PersonalizationSection />;
    case "projects":
      return <ProjectsSection />;
    case "models":
      return <ModelsSection />;
    case "agent":
      return <AgentSection />;
    case "usage":
      return <UsageSection />;
    case "memory":
      return <MemorySection />;
    case "connections":
      return <ConnectionsSection />;
    default:
      return <DataSection />;
  }
}

export default function SettingsPage() {
  const { t } = useI18n();
  const [section, setSection] = useState("models");

  // The address (?section=…) names the section, so a link can open a specific one.
  useEffect(() => {
    const timer = setTimeout(() => {
      const s = new URLSearchParams(window.location.search).get("section");
      if (s && IDS.includes(s)) setSection(s);
    }, 0);
    return () => clearTimeout(timer);
  }, []);
  const go = (id: string) => {
    setSection(id);
    window.history.replaceState(null, "", `?section=${id}`);
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl px-6 py-8">
        <h1 className="font-serif text-3xl font-semibold">{t("Settings")}</h1>
        <p className="mt-1 text-sm text-soft">{t("Manage your profile, preferences, projects and models.")}</p>
        <div className="mt-6 grid gap-6 md:grid-cols-[13rem_minmax(0,1fr)]">
          <nav aria-label={t("Settings sections")} className="space-y-4">
            {GROUPS.map((g) => (
              <div key={g.label}>
                <p className="mb-1 px-2 text-[11px] tracking-wider text-soft">{t(g.label)}</p>
                <ul className="flex flex-wrap gap-1 md:block md:space-y-0.5">
                  {g.items.map((i) => (
                    <li key={i.id}>
                      <button
                        type="button"
                        aria-current={section === i.id ? "page" : undefined}
                        onClick={() => go(i.id)}
                        className={`flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-sm ${section === i.id ? "bg-accent-soft font-medium text-accent" : "text-soft hover:bg-card hover:text-ink"}`}
                      >
                        <span className="w-4 text-center" aria-hidden="true">
                          {i.icon}
                        </span>
                        {t(i.label)}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </nav>
          <main className="min-w-0">
            <Section id={section} />
          </main>
        </div>
      </div>
    </div>
  );
}
