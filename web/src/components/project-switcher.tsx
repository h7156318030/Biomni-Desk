"use client";

import { useEffect, useRef, useState } from "react";
import type { Project } from "@/lib/api";
import { tr, useI18n } from "@/lib/i18n";

export const ALL = "all";

/** Picks which project's tasks the sidebar shows; also creates, renames and deletes projects. */
export function ProjectSwitcher({
  projects,
  current,
  onSelect,
  onCreate,
  onRename,
  onDelete,
  disabled,
}: {
  projects: Project[];
  current: string;
  onSelect: (id: string) => void;
  onCreate: (name: string) => Promise<string | null>;
  onRename: (id: string, name: string) => Promise<string | null>;
  onDelete: (id: string) => Promise<string | null>;
  disabled?: boolean;
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const shown = current === ALL ? t("All recent tasks") : t(projects.find((p) => p.id === current)?.name ?? "Quick task");
  const cur = projects.find((p) => p.id === current);
  const fail = (msg: string | null) => {
    setError(msg);
    return msg === null;
  };

  return (
    <div ref={box} className="relative">
      <div className="flex items-center gap-1">
        <button
          type="button"
          role="combobox"
          aria-expanded={open}
          aria-controls="project-list"
          aria-label={t("Choose project")}
          onClick={() => setOpen((o) => !o)}
          className="flex min-w-0 flex-1 items-center justify-between gap-2 rounded-lg px-1 py-1 text-left hover:bg-card"
        >
          <span className="min-w-0">
            <span className="block text-[10px] tracking-wider text-soft">{t("Project")}</span>
            <span className="block truncate font-serif text-lg font-semibold leading-tight">{shown}</span>
          </span>
          <span className="text-xs text-soft">▾</span>
        </button>
        {cur && !cur.default && (
          <button
            type="button"
            title={t("Project settings")}
            aria-label={t("Project settings")}
            disabled={disabled}
            onClick={async () => {
              const name = window.prompt(tr("Project name (leave empty and confirm = no change)"), cur.name);
              if (name && name.trim() && name.trim() !== cur.name) fail(await onRename(cur.id, name.trim()));
              else if (name === "" && window.confirm(tr("Delete project “{name}”? Its tasks are kept and moved back to “Quick task”.", { name: cur.name })))
                fail(await onDelete(cur.id));
            }}
            className="rounded-md px-1.5 py-1 text-soft hover:bg-card hover:text-accent"
          >
            ⚙
          </button>
        )}
      </div>

      {open && (
        <div id="project-list" role="listbox" className="absolute left-0 right-0 z-30 mt-1 overflow-hidden rounded-xl border border-line bg-panel py-1 shadow-lg">
          {projects.map((p) => (
            <button
              key={p.id}
              type="button"
              role="option"
              aria-selected={p.id === current}
              onClick={() => {
                onSelect(p.id);
                setOpen(false);
              }}
              className={`flex w-full items-center justify-between gap-2 px-3 py-1.5 text-left text-sm ${p.id === current ? "bg-accent-soft" : "hover:bg-card"}`}
            >
              <span className="truncate">
                {p.default ? t(p.name) : p.name}
                {p.default && <span className="ml-1 text-xs text-soft">{t(" (default)")}</span>}
              </span>
              <span className="shrink-0 text-xs text-soft">{p.count}</span>
            </button>
          ))}
          <div className="my-1 border-t border-line" />
          <button
            type="button"
            role="option"
            aria-selected={current === ALL}
            onClick={() => {
              onSelect(ALL);
              setOpen(false);
            }}
            className={`block w-full px-3 py-1.5 text-left text-sm ${current === ALL ? "bg-accent-soft" : "hover:bg-card"}`}
          >
            {t("All recent tasks")}
          </button>
          <button
            type="button"
            onClick={async () => {
              const name = window.prompt(tr("Name of the new project"));
              if (name?.trim() && fail(await onCreate(name.trim()))) setOpen(false);
            }}
            className="block w-full px-3 py-1.5 text-left text-sm text-accent hover:bg-card"
          >
            {t("＋ Create new project")}
          </button>
          {error && <p className="px-3 py-1 text-xs text-warn">{error}</p>}
        </div>
      )}
    </div>
  );
}

/** "Move": move the open task to another project. */
export function TransferMenu({
  projects,
  current,
  onMove,
  onCreateAndMove,
}: {
  projects: Project[];
  current: string;
  onMove: (id: string) => void;
  onCreateAndMove: (name: string) => void;
}) {
  const { t } = useI18n();
  const menu = useRef<HTMLDetailsElement>(null);
  return (
    <details ref={menu} className="relative">
      <summary className="cursor-pointer list-none rounded-md border border-line px-2 py-0.5 text-xs text-soft marker:content-none hover:border-accent">
        {t("Move")}
      </summary>
      <div className="absolute right-0 top-full z-30 mt-1 w-44 overflow-hidden rounded-xl border border-line bg-panel py-1 shadow-lg">
        <p className="px-3 py-1 text-xs text-soft">{t("Move this task to…")}</p>
        {projects.map((p) => (
          <button
            key={p.id}
            type="button"
            disabled={p.id === current}
            onClick={() => {
              onMove(p.id);
              menu.current?.removeAttribute("open");
            }}
            className="block w-full truncate px-3 py-1.5 text-left text-sm hover:bg-accent-soft disabled:opacity-40"
          >
            {p.default ? t(p.name) : p.name}
            {p.id === current && t(" (current)")}
          </button>
        ))}
        <div className="my-1 border-t border-line" />
        <button
          type="button"
          onClick={() => {
            const name = window.prompt(tr("Name of the new project (the task will move into it)"));
            menu.current?.removeAttribute("open");
            if (name?.trim()) onCreateAndMove(name.trim());
          }}
          className="block w-full px-3 py-1.5 text-left text-sm text-accent hover:bg-accent-soft"
        >
          {t("＋ New project and move")}
        </button>
      </div>
    </details>
  );
}
