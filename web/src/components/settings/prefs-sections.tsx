"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { getPrefs, putPrefs, type Prefs, type Profile } from "@/lib/api";
import { applyLook } from "@/lib/theme";
import { useI18n } from "@/lib/i18n";
import { Card, Field, ListEditor, SaveBadge, Segmented, Toggle, inputCls, useAutosave } from "@/components/settings/ui";

type State = { profile: Profile; prefs: Prefs; areas: string[] };

/** Loads the saved profile and preferences, and saves them again a moment after any change. */
function usePrefs() {
  const [data, setData] = useState<State | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    getPrefs()
      .then((v) => alive && setData(v))
      .catch((e) => alive && setLoadError(e instanceof Error ? e.message : String(e)));
    return () => {
      alive = false;
    };
  }, []);

  const value = useMemo(() => (data ? { profile: data.profile, prefs: data.prefs } : null), [data]);
  const save = useCallback(async (v: { profile: Profile; prefs: Prefs }) => {
    const saved = await putPrefs(v);
    applyLook({ style: saved.prefs.style, appearance: saved.prefs.appearance });
  }, []);
  const status = useAutosave(value, save);
  const setProfile = (p: Partial<Profile>) => setData((d) => (d ? { ...d, profile: { ...d.profile, ...p } } : d));
  const setPrefs = (p: Partial<Prefs>) => {
    setData((d) => (d ? { ...d, prefs: { ...d.prefs, ...p } } : d));
    // the look changes at once, not after the save
    if (p.style || p.appearance) applyLook({ style: p.style ?? data?.prefs.style ?? "classic", appearance: p.appearance ?? data?.prefs.appearance ?? "auto" });
  };
  return { data, loadError, status, setProfile, setPrefs };
}

function Loading({ error }: { error: string | null }) {
  const { t } = useI18n();
  return <p className={`text-sm ${error ? "text-warn" : "text-soft"}`}>{error ? t("Failed to read: {error}", { error }) : t("Loading…")}</p>;
}

export function ProfileSection() {
  const { t } = useI18n();
  const { data, loadError, status, setProfile } = usePrefs();
  if (!data) return <Loading error={loadError} />;
  const p = data.profile;
  const text = (key: keyof Profile, label: string, placeholder = "") => (
    <Field label={label}>
      <input className={inputCls} value={p[key] as string} placeholder={placeholder} onChange={(e) => setProfile({ [key]: e.target.value })} />
    </Field>
  );
  return (
    <div className="space-y-4">
      <Card
        title={t("Profile")}
        hint={t(
          "This information goes to the agent with every task, so it knows who you are. For example, when searching papers by author, it can use your institution and research areas to tell apart authors with the same name. It is stored only on this computer.",
        )}
      >
        <div className="grid gap-4 sm:grid-cols-2">
          {text("last_name", t("Last name"))}
          {text("first_name", t("First name"))}
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          {text("institution", t("Institution"))}
          {text("position", t("Position"))}
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          {text("orcid", "ORCID iD", "0000-0000-0000-0000")}
          {text("scholar", t("Google Scholar link"))}
          {text("website", t("Lab or personal website"))}
        </div>
        <Field label={t("Research areas")} hint={t("Select any number")}>
          <div className="flex flex-wrap gap-1.5">
            {data.areas.map((a) => {
              const on = p.areas.includes(a);
              return (
                <button
                  key={a}
                  type="button"
                  aria-pressed={on}
                  onClick={() => setProfile({ areas: on ? p.areas.filter((x) => x !== a) : [...p.areas, a] })}
                  className={`rounded-full border px-3 py-1 text-sm ${on ? "border-accent bg-accent-soft text-accent" : "border-line text-soft hover:border-accent"}`}
                >
                  {on && "✓ "}
                  {a}
                </button>
              );
            })}
          </div>
        </Field>
        <SaveBadge {...status} />
      </Card>
    </div>
  );
}

export function PersonalizationSection() {
  const { t } = useI18n();
  const { data, loadError, status, setPrefs } = usePrefs();
  if (!data) return <Loading error={loadError} />;
  const f = data.prefs;
  return (
    <div className="space-y-4">
      <Card title={t("Personalisation")} hint={t("Each option really changes how the agent works or how pages look.")}>
        <Field label={t("Preferred language")} hint={t("Which language the agent prefers when it writes code.")}>
          <Segmented
            label={t("Preferred language")}
            value={f.language}
            onChange={(v) => setPrefs({ language: v })}
            options={[
              { id: "python", label: "Python" },
              { id: "r", label: "R" },
              { id: "any", label: t("Any") },
            ]}
          />
        </Field>
        <Field label={t("Image output format")} hint={t("Which format the agent prefers when saving images.")}>
          <Segmented
            label={t("Image output format")}
            value={f.image_format}
            onChange={(v) => setPrefs({ image_format: v })}
            options={[
              { id: "png", label: "PNG" },
              { id: "svg", label: "SVG" },
              { id: "any", label: t("Any") },
            ]}
          />
        </Field>
        <Field label={t("Interface style")} hint={t("Choose the look of borders and dividers.")}>
          <Segmented
            label={t("Interface style")}
            value={f.style}
            onChange={(v) => setPrefs({ style: v })}
            options={[
              { id: "classic", label: t("Classic"), hint: t("Clear borders, accent colour emphasised") },
              { id: "modern", label: t("Modern"), hint: t("Soft borders, lighter") },
            ]}
          />
        </Field>
        <Field label={t("Appearance")} hint={t("Light, dark, or follow the system.")}>
          <Segmented
            label={t("Appearance")}
            value={f.appearance}
            onChange={(v) => setPrefs({ appearance: v })}
            options={[
              { id: "auto", label: t("Follow system") },
              { id: "light", label: t("Light") },
              { id: "dark", label: t("Dark") },
            ]}
          />
        </Field>
      </Card>

      <Card
        title={t("Custom instructions")}
        hint={t("Standing requirements added to every task you start, e.g. “answer in English”, “every citation must include a PMID”.")}
      >
        <ListEditor items={f.instructions} onChange={(v) => setPrefs({ instructions: v })} placeholder={t("Write an instruction and press Enter to add it")} max={20} />
      </Card>

      <Card title={t("Behaviour")}>
        <Toggle
          checked={f.use_last_results}
          onChange={(v) => setPrefs({ use_last_results: v })}
          label={t("Use results from the last session")}
          hint={t("When on, the agent knows which files were produced earlier in the same project and can read them when needed. When off, each task starts from scratch.")}
        />
        <Toggle
          checked={f.auto_review}
          onChange={(v) => setPrefs({ auto_review: v })}
          label={t("Automatic review")}
          badge={t("Experimental")}
          hint={t("After each answer, the model checks it again against a checklist and the result appears under the answer (one extra model call).")}
        />
        <SaveBadge {...status} />
      </Card>
    </div>
  );
}
