"use client";

import { useEffect, useState } from "react";
import { resolveRefs, type RefMeta } from "./api";
import type { Reference } from "./citations";

// Shared across answers so the same paper is looked up once per page load.
const known = new Map<string, RefMeta>();
const pending = new Map<string, Promise<void>>();

/** Title / authors / journal / year for the verified references of an answer, filled in as they arrive. */
export function useRefMeta(refs: Reference[]): Record<string, RefMeta> {
  const [, bump] = useState(0);
  const need = refs
    .filter((r) => (r.kind !== "db" || !r.verified) && !known.has(r.key) && !pending.has(r.key))
    .map((r) => ({ kind: r.key.split(":")[0], id: r.key.slice(r.key.indexOf(":") + 1) }));
  const sig = need.map((n) => `${n.kind}:${n.id}`).join("|");

  useEffect(() => {
    if (!sig) return;
    let alive = true;
    const items = sig.split("|").map((k) => ({ kind: k.split(":")[0], id: k.slice(k.indexOf(":") + 1) }));
    const p = resolveRefs(items)
      .then((r) => {
        for (const [k, v] of Object.entries(r)) known.set(k, v);
      })
      .catch(() => {})
      .finally(() => {
        for (const it of items) pending.delete(`${it.kind}:${it.id}`);
        if (alive) bump((n) => n + 1);
      });
    for (const it of items) pending.set(`${it.kind}:${it.id}`, p);
    return () => {
      alive = false;
    };
  }, [sig]);

  const out: Record<string, RefMeta> = {};
  for (const r of refs) {
    const m = known.get(r.key);
    if (m) out[r.key] = m;
  }
  return out;
}
