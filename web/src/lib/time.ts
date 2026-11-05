import { tr } from "@/lib/i18n";

/** "just now / 5 min ago / 3 h ago / 2 d ago / 1 wk ago / 3 mo ago" for a unix timestamp in seconds. */
export function relativeTime(ts: number, now: number = Date.now() / 1000): string {
  const d = Math.max(0, now - ts);
  if (d < 60) return tr("just now");
  if (d < 3600) return tr("{n} min ago", { n: Math.floor(d / 60) });
  if (d < 86400) return tr("{n} h ago", { n: Math.floor(d / 3600) });
  if (d < 86400 * 7) return tr("{n} d ago", { n: Math.floor(d / 86400) });
  if (d < 86400 * 30) return tr("{n} wk ago", { n: Math.floor(d / (86400 * 7)) });
  if (d < 86400 * 365) return tr("{n} mo ago", { n: Math.floor(d / (86400 * 30)) });
  return tr("{n} y ago", { n: Math.floor(d / (86400 * 365)) });
}
