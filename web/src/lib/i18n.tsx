"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { zh } from "@/lib/messages/zh";

/**
 * The interface languages. English is the default and the source language:
 * every string in the code is written in English and used as its own key.
 * The Chinese dictionary (messages/zh.ts) maps those English strings to Chinese.
 * A string with no translation simply shows in English.
 */
export type Lang = "en" | "zh";
export type Translate = (text: string, vars?: Record<string, string | number>) => string;

const STORAGE_KEY = "biomni.lang";
const DICTIONARIES: Record<Lang, Record<string, string>> = { en: {}, zh };

/** The language currently on screen. Plain functions (outside React components) read it with tr(). */
let activeLang: Lang = "en";

export function currentLang(): Lang {
  return activeLang;
}

/** Translate outside a React component. Components should use the hook, so they re-render when the language changes. */
export const tr: Translate = (text, vars) => {
  let out = DICTIONARIES[activeLang][text] ?? text;
  if (vars) for (const [name, value] of Object.entries(vars)) out = out.split(`{${name}}`).join(String(value));
  return out;
};

type I18n = { lang: Lang; setLang: (lang: Lang) => void; t: Translate };

const I18nContext = createContext<I18n | null>(null);

function savedLang(): Lang | null {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY);
    return value === "en" || value === "zh" ? value : null;
  } catch {
    return null; // private windows and blocked storage: the default language is used
  }
}

/** Provides the interface language to the whole app. */
export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>("en");
  activeLang = lang;

  // Read the saved choice after mounting, so the server render and the first browser render match.
  useEffect(() => {
    const saved = savedLang();
    if (saved) setLangState(saved);
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
    // The tab title comes from the static page metadata (English); translate it for the current language.
    document.title = DICTIONARIES[lang]["Biomni-Lite workspace"] ?? "Biomni-Lite workspace";
  }, [lang]);

  const setLang = useCallback((next: Lang) => {
    activeLang = next;
    setLangState(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // the choice still applies for this page view
    }
  }, []);

  const t = useCallback<Translate>((text, vars) => {
    let out = DICTIONARIES[lang][text] ?? text;
    if (vars) for (const [name, value] of Object.entries(vars)) out = out.split(`{${name}}`).join(String(value));
    return out;
  }, [lang]);

  const value = useMemo(() => ({ lang, setLang, t }), [lang, setLang, t]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18n {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used inside I18nProvider");
  return ctx;
}
