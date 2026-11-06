"use client";

import { useMemo, useState } from "react";
import { downloadUrl, downloadZip, fileUrl, type Artifact } from "@/lib/api";
import { FileActions } from "@/components/file-actions";
import { currentLang, useI18n } from "@/lib/i18n";

const ICON: Record<Artifact["kind"], string> = { image: "🖼", video: "▶", pdf: "📄", table: "▦", html: "◧", text: "≡" };

export function formatSize(n?: number): string {
  if (n === undefined) return "";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export function formatStamp(ts?: number): string {
  if (!ts) return "";
  const d = new Date(ts * 1000);
  const p = (n: number) => String(n).padStart(2, "0");
  const clock = `${p(d.getHours())}:${p(d.getMinutes())}`;
  if (currentLang() === "zh") return `${d.getMonth() + 1}月${d.getDate()}日 ${clock}`;
  return `${d.toLocaleDateString("en-US", { month: "short", day: "numeric" })} ${clock}`;
}

/** Folder parts of each file, relative to the folder all the files share, so a flat result set shows no folders at all. */
export function relativeDirs(paths: string[]): string[][] {
  const dirs = paths.map((p) => p.replace(/\\/g, "/").split("/").slice(0, -1));
  if (!dirs.length) return [];
  let common = dirs[0].length;
  for (const d of dirs) {
    let i = 0;
    while (i < common && i < d.length && d[i] === dirs[0][i]) i++;
    common = i;
  }
  return dirs.map((d) => d.slice(common));
}

type Entry = { kind: "folder"; name: string; count: number; mtime: number } | { kind: "file"; file: Artifact };

/** The files and sub-folders directly inside `cwd` (a list of folder names from the root). */
export function listFolder(artifacts: Artifact[], cwd: string[]): Entry[] {
  const rel = relativeDirs(artifacts.map((a) => a.path));
  const folders = new Map<string, { count: number; mtime: number }>();
  const files: Entry[] = [];
  artifacts.forEach((a, i) => {
    const parts = rel[i];
    if (cwd.some((c, j) => parts[j] !== c)) return;
    if (parts.length === cwd.length) files.push({ kind: "file", file: a });
    else {
      const name = parts[cwd.length];
      const cur = folders.get(name) ?? { count: 0, mtime: 0 };
      folders.set(name, { count: cur.count + 1, mtime: Math.max(cur.mtime, a.mtime ?? 0) });
    }
  });
  return [...[...folders].map(([name, v]) => ({ kind: "folder" as const, name, ...v })), ...files];
}

/** Files produced by the task: folders, filter, sort, select several, open / download / jump to the step that made it. */
export function ResultsPanel({
  artifacts,
  onOpen,
  onViewSource,
  onDetails,
  onRefresh,
}: {
  artifacts: Artifact[];
  onOpen?: (a: Artifact) => void;
  onViewSource?: (a: Artifact) => void;
  onDetails?: (a: Artifact) => void;
  onRefresh?: () => void;
}) {
  const { t } = useI18n();
  const [query, setQuery] = useState("");
  const [newestFirst, setNewestFirst] = useState(true);
  const [grid, setGrid] = useState(false);
  const [cwd, setCwd] = useState<string[]>([]);
  const [chosen, setChosen] = useState<string[]>([]);
  const [zipError, setZipError] = useState<string | null>(null);

  const entries = useMemo(() => {
    const q = query.trim().toLowerCase();
    const rows = (q ? artifacts.filter((a) => a.name.toLowerCase().includes(q)).map((file) => ({ kind: "file" as const, file })) : listFolder(artifacts, cwd)) as Entry[];
    const time = (e: Entry) => (e.kind === "file" ? (e.file.mtime ?? 0) : e.mtime);
    return [...rows].sort((a, b) => (a.kind === b.kind ? (time(a) - time(b)) * (newestFirst ? -1 : 1) : a.kind === "folder" ? -1 : 1));
  }, [artifacts, query, newestFirst, cwd]);
  const files = entries.flatMap((e) => (e.kind === "file" ? [e.file] : []));
  const validChosen = chosen.filter((p) => artifacts.some((a) => a.path === p));

  const toggle = (path: string) => setChosen((c) => (c.includes(path) ? c.filter((x) => x !== path) : [...c, path]));
  const download = async (paths: string[]) => {
    setZipError(null);
    try {
      await downloadZip(paths);
    } catch (e) {
      setZipError(e instanceof Error ? e.message : String(e));
    }
  };

  const tool = "shrink-0 rounded-md border border-line bg-card px-2 py-1 text-xs text-soft hover:border-accent disabled:opacity-40";
  return (
    <div>
      {zipError && <p className="mb-1 text-xs text-warn">{zipError}</p>}
      <div className="mb-2 flex items-center gap-1.5">
        {onRefresh && (
          <button type="button" onClick={onRefresh} title={t("Refresh results")} aria-label={t("Refresh results")} className={tool}>
            ↻
          </button>
        )}
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("Filter files…")}
          aria-label={t("Filter files")}
          className="min-w-0 flex-1 rounded-md border border-line bg-card px-2.5 py-1 text-sm outline-none focus:border-accent"
        />
        <button type="button" onClick={() => setNewestFirst((v) => !v)} title={t("Sort by time")} className={tool}>
          {t("Time")} {newestFirst ? "↓" : "↑"}
        </button>
        <button type="button" onClick={() => setGrid((g) => !g)} title={grid ? t("Switch to list") : t("Switch to grid")} aria-pressed={grid} className={tool}>
          {grid ? "▤" : "▦"}
        </button>
        <button
          type="button"
          disabled={!artifacts.length}
          onClick={() => download(validChosen.length ? validChosen : files.length ? files.map((f) => f.path) : artifacts.map((a) => a.path))}
          title={validChosen.length ? t("Download the {n} selected files (zip)", { n: validChosen.length }) : t("Download all (zip)")}
          className={tool}
        >
          ⤓{validChosen.length > 0 && <span className="ml-0.5">{validChosen.length}</span>}
        </button>
      </div>

      {(cwd.length > 0 || artifacts.length > 0) && !query && (
        <nav aria-label={t("Folders")} className="mb-1.5 flex flex-wrap items-center gap-1 text-xs text-soft">
          <button type="button" onClick={() => setCwd([])} title={t("Back to root")} aria-label={t("Root")} className="hover:text-accent">
            ⌂
          </button>
          {cwd.map((name, i) => (
            <span key={`${name}-${i}`} className="flex items-center gap-1">
              ›
              <button type="button" onClick={() => setCwd(cwd.slice(0, i + 1))} className="hover:text-accent">
                {name}
              </button>
            </span>
          ))}
        </nav>
      )}

      {artifacts.length === 0 ? (
        <p className="text-sm text-soft">{t("Generated figures, tables and files appear here.")}</p>
      ) : entries.length === 0 ? (
        <p className="text-sm text-soft">{t("No matching files.")}</p>
      ) : grid ? (
        <ul className="grid grid-cols-2 gap-2">
          {entries.map((e) =>
            e.kind === "folder" ? (
              <li key={`d-${e.name}`}>
                <button type="button" onClick={() => setCwd([...cwd, e.name])} className="grid h-full w-full place-items-center rounded-lg border border-line bg-card p-3 text-sm hover:border-accent">
                  <span className="text-2xl text-soft">📁</span>
                  <span className="max-w-full truncate">{e.name}</span>
                  <span className="text-xs text-soft">{t("{n} files", { n: e.count })}</span>
                </button>
              </li>
            ) : (
              <li key={e.file.path}>
                <a
                  href={fileUrl(e.file.path)}
                  target="_blank"
                  rel="noreferrer"
                  title={e.file.name}
                  onClick={(ev) => {
                    if (onOpen && !ev.ctrlKey && !ev.metaKey) {
                      ev.preventDefault();
                      onOpen(e.file);
                    }
                  }}
                  className="block overflow-hidden rounded-lg border border-line bg-card hover:border-accent"
                >
                  {e.file.kind === "image" ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={fileUrl(e.file.path)} alt={e.file.name} className="h-20 w-full bg-white object-cover" />
                  ) : (
                    <span className="grid h-20 place-items-center text-2xl text-soft">{ICON[e.file.kind]}</span>
                  )}
                  <span className="block truncate px-2 py-1 text-xs">{e.file.name}</span>
                </a>
              </li>
            ),
          )}
        </ul>
      ) : (
        <ul className="space-y-0.5">
          {entries.map((e) =>
            e.kind === "folder" ? (
              <li key={`d-${e.name}`}>
                <button type="button" onClick={() => setCwd([...cwd, e.name])} className="flex w-full items-center gap-2 rounded-lg px-1.5 py-1.5 text-left text-sm hover:bg-card">
                  <span className="w-4 shrink-0 text-center text-soft" aria-hidden="true">
                    📁
                  </span>
                  <span className="min-w-0 flex-1 truncate">{e.name}</span>
                  <span className="shrink-0 text-xs text-soft">{e.count}</span>
                  <span className="text-soft">›</span>
                </button>
              </li>
            ) : (
              <li key={e.file.path} className="group rounded-lg border border-transparent px-1.5 py-1.5 hover:border-line hover:bg-card">
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={validChosen.includes(e.file.path)}
                    onChange={() => toggle(e.file.path)}
                    aria-label={t("Select {name}", { name: e.file.name })}
                    className="h-3.5 w-3.5 shrink-0 accent-[var(--accent)]"
                  />
                  <span className="w-4 shrink-0 text-center text-soft" aria-hidden="true">
                    {ICON[e.file.kind]}
                  </span>
                  <a
                    href={fileUrl(e.file.path)}
                    target="_blank"
                    rel="noreferrer"
                    className="min-w-0 flex-1 truncate text-sm"
                    title={e.file.name}
                    onClick={(ev) => {
                      if (onOpen && !ev.ctrlKey && !ev.metaKey) {
                        ev.preventDefault();
                        onOpen(e.file);
                      }
                    }}
                  >
                    {e.file.name}
                  </a>
                  {onDetails && (
                    <button
                      type="button"
                      onClick={() => onDetails(e.file)}
                      title={t("Versions, provenance and comments")}
                      aria-label={t("Open details of {name}", { name: e.file.name })}
                      className="shrink-0 text-xs text-soft hover:text-accent"
                    >
                      {t("Details")}
                    </button>
                  )}
                  {onViewSource && (
                    <button
                      type="button"
                      onClick={() => onViewSource(e.file)}
                      title={t("See the step in the working trace that produced it")}
                      aria-label={t("Show source step")}
                      className="shrink-0 text-soft hover:text-accent"
                    >
                      ⌕
                    </button>
                  )}
                  <a href={downloadUrl(e.file.path)} title={t("Download")} aria-label={t("Download {name}", { name: e.file.name })} className="shrink-0 text-soft hover:text-accent">
                    ⤓
                  </a>
                </div>
                <div className="ml-10 text-xs text-soft">
                  {formatStamp(e.file.mtime)}
                  {e.file.size !== undefined && ` · ${formatSize(e.file.size)}`}
                </div>
                <div className="ml-10 mt-0.5">
                  <FileActions path={e.file.path} compact />
                </div>
                {e.file.kind === "image" && (
                  <a href={fileUrl(e.file.path)} target="_blank" rel="noreferrer" className="ml-10 mt-1 hidden group-hover:block">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={fileUrl(e.file.path)} alt={e.file.name} className="max-h-32 rounded border border-line bg-white" />
                  </a>
                )}
              </li>
            ),
          )}
        </ul>
      )}
    </div>
  );
}
