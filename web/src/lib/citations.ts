import type { AgentEvent } from "./api";
import { tr } from "@/lib/i18n";

export type Source = {
  id: number; // position in the ledger
  key: string; // pmid:123 | doi:10.x/y | url:https://...
  label: string;
  href: string;
  title?: string;
  kind: "paper" | "db" | "web";
  reader: boolean; // false for raw API endpoints that were fetched but are not something a reader would open
};

// An address ends at a space, a bracket or quote (ASCII or full-width), CJK punctuation, or the ** that closes bold text.
const URL_RE = /https?:\/\/[^\s"'<>)\]}，。；、（）【】《》［］“”‘’：*]+/g;
const DOI_RE = /\b10\.\d{4,9}\/[^\s"'<>)\]}，。；、（）【】《》［］“”‘’：*]+/g;
const PMID_RE = /PMID[:\s]*(\d{6,9})/g;
const API_RE = /rest\.uniprot|rest\.ensembl|\/api\/|\.json(\?|$)|eutils\.ncbi/;

const trimEnd = (s: string) => s.replace(/[.,;:]+$/, "");

/** The search tool appends ?utm_source=openai to the links it hands over; the same page without it is the same source. */
const canon = (u: string) => nu(u).replace(/^https?:\/\//i, "").replace(/^www\./i, "").replace(/#.*$/, "").replace(/\/index\.html?$/i, "").replace(/\/+$/, "").toLowerCase();
const nu = (u: string) => u.replace(/\?utm_source=openai&/g, "?").replace(/[?&]utm_source=openai(?=&|#|$)/g, "");

/** Known database API endpoints, mapped to the page a person would open instead of raw JSON. */
export function readerUrl(url: string): { href: string; label: string } | null {
  let m = /rest\.uniprot\.org\/uniprotkb\/([A-Z][A-Z0-9]{5,9})(?:\.json|\.fasta|\.txt)?(?:[?#].*)?$/i.exec(url);
  if (m) return { href: `https://www.uniprot.org/uniprotkb/${m[1].toUpperCase()}/entry`, label: `UniProt ${m[1].toUpperCase()}` };
  m = /rest\.uniprot\.org\/uniprotkb\/search\?(?:.*&)?query=([^&]+)/i.exec(url);
  if (m) return { href: `https://www.uniprot.org/uniprotkb?query=${m[1]}`, label: tr("UniProt search: {query}", { query: decodeURIComponent(m[1]).slice(0, 40) }) };
  m = /rest\.ensembl\.org\/lookup\/id\/(ENS[A-Z]*G\d+)/i.exec(url);
  if (m) return { href: `https://www.ensembl.org/id/${m[1]}`, label: `Ensembl ${m[1]}` };
  m = /rest\.ensembl\.org\/lookup\/symbol\/[a-z_]+\/([A-Za-z0-9._-]+)/i.exec(url);
  if (m) return { href: `https://www.ensembl.org/Multi/Search/Results?q=${m[1]}`, label: `Ensembl ${m[1]}` };
  m = /eutils\.ncbi\.nlm\.nih\.gov\/entrez\/eutils\/\w+\.fcgi\?(?:.*&)?db=clinvar&(?:.*&)?id=(\d+)/i.exec(url);
  if (m) return { href: `https://www.ncbi.nlm.nih.gov/clinvar/variation/${m[1]}/`, label: `ClinVar ${m[1]}` };
  m = /eutils\.ncbi\.nlm\.nih\.gov\/entrez\/eutils\/\w+\.fcgi\?(?:.*&)?db=pubmed&(?:.*&)?id=(\d+)/i.exec(url);
  if (m) return { href: `https://pubmed.ncbi.nlm.nih.gov/${m[1]}/`, label: `PubMed ${m[1]}` };
  m = /rest\.rcsb\.org\/.*\/entry\/([0-9A-Za-z]{4})/i.exec(url);
  if (m) return { href: `https://www.rcsb.org/structure/${m[1].toUpperCase()}`, label: `PDB ${m[1].toUpperCase()}` };
  m = /rest\.genenames\.org\/fetch\/symbol\/([A-Za-z0-9-]+)/i.exec(url);
  if (m) return { href: `https://www.genenames.org/tools/search/#!/?query=${m[1]}`, label: `HGNC ${m[1]}` };
  return null;
}

/** Nearest "Title: ..." line just before `index`, which is how the search tools print their records. */
function titleBefore(text: string, index: number): string | undefined {
  const window = text.slice(Math.max(0, index - 400), index);
  const all = [...window.matchAll(/Title:\s*([^\n]+)/g)];
  const last = all[all.length - 1];
  return last ? last[1].trim().slice(0, 160) : undefined;
}

/**
 * Every URL, DOI and PMID that a tool actually returned or the agent actually fetched.
 * This is the ledger an answer's citations are checked against.
 */
export function buildLedger(events: AgentEvent[]): Source[] {
  const map = new Map<string, Omit<Source, "id">>();
  const add = (key: string, label: string, href: string, kind: Source["kind"], reader: boolean, title?: string) => {
    const prev = map.get(key);
    if (!prev) map.set(key, { key, label, href, kind, reader, title });
    else if (!prev.title && title) prev.title = title;
  };
  for (const e of events) {
    if (e.type === "tool") {
      // Results of the model's own searches: the address and title are known exactly.
      for (const raw of e.results ?? []) {
        const r = { ...raw, url: nu(raw.url) };
        const pm = /pubmed\.ncbi\.nlm\.nih\.gov\/(\d{4,9})/.exec(r.url);
        if (pm) add(`pmid:${pm[1]}`, `PMID ${pm[1]}`, `https://pubmed.ncbi.nlm.nih.gov/${pm[1]}/`, "paper", true, r.title);
        const dm = /doi\.org\/(10\.\d{4,9}\/\S+)/.exec(r.url);
        if (dm) add(`doi:${dm[1]}`, `DOI ${dm[1]}`, `https://doi.org/${dm[1]}`, "paper", true, r.title);
        const db = readerUrl(r.url);
        if (db) add(`url:${r.url}`, db.label, db.href, "db", true, r.title);
        else add(`url:${r.url}`, r.domain || r.url, r.url, "web", true, r.title);
      }
    }
    const text =
      e.type === "observation" ? e.text : e.type === "code" ? e.code : e.type === "tool" ? `${e.text ?? ""}` : "";
    if (!text) continue;
    for (const m of text.matchAll(URL_RE)) {
      const url = nu(trimEnd(m[0]));
      const db = readerUrl(url);
      if (db) add(`url:${url}`, db.label, db.href, "db", true);
      else add(`url:${url}`, url.replace(/^https?:\/\//, "").slice(0, 60), url, "web", !API_RE.test(url), titleBefore(text, m.index ?? 0));
    }
    for (const m of text.matchAll(DOI_RE)) {
      const doi = trimEnd(m[0]);
      add(`doi:${doi}`, `DOI ${doi}`, `https://doi.org/${doi}`, "paper", true, titleBefore(text, m.index ?? 0));
    }
    for (const m of text.matchAll(PMID_RE)) {
      add(`pmid:${m[1]}`, `PMID ${m[1]}`, `https://pubmed.ncbi.nlm.nih.gov/${m[1]}/`, "paper", true, titleBefore(text, m.index ?? 0));
    }
  }
  return [...map.values()].map((s, i) => ({ id: i + 1, ...s }));
}

/** The reader-facing part of the ledger, for the side panel. */
export const collectSources = (events: AgentEvent[]): Source[] => buildLedger(events).filter((s) => s.reader);

export type Reference = {
  n: number;
  key: string;
  kind: Source["kind"];
  verified: boolean; // seen in this task's tool output
  weak?: boolean; // not in the tool output, but confirmed to exist (PubMed / Crossref / the page answered)
  label: string;
  href?: string;
  title?: string;
};

// "DOI:" in front of a DOI is swallowed too, so the marker replaces the whole mention.
const TOKEN_RE = new RegExp(`${PMID_RE.source}|(?:DOI[:：\\s]*)?(${DOI_RE.source})|(${URL_RE.source})`, "g");

/**
 * Rewrite an answer so every PMID / DOI / URL mention becomes a numbered marker [n], numbered in order of
 * first mention, and return the matching reference list. A mention that no tool output contained becomes
 * a "[n?]" marker and an unverified reference, so a made-up citation can never look verified.
 */
export type Resolved = Record<string, { title?: string; ok?: boolean; kind?: string; doi?: string }>;

function hrefOf(key: string): string {
  const id = key.slice(key.indexOf(":") + 1);
  if (key.startsWith("pmid:")) return `https://pubmed.ncbi.nlm.nih.gov/${id}/`;
  if (key.startsWith("doi:")) return `https://doi.org/${id}`;
  return id;
}

/** A cited address that was not in the tool output but exists. Known database endpoints show as the page a reader opens. */
function weakRef(n: number, key: string, label: string, title?: string): Reference {
  if (key.startsWith("url:")) {
    const db = readerUrl(key.slice(4));
    if (db) return { n, key, kind: "db", verified: false, weak: true, label: db.label, href: db.href };
    return { n, key, kind: "web", verified: false, weak: true, label, href: hrefOf(key), title };
  }
  return { n, key, kind: "paper", verified: false, weak: true, label, href: hrefOf(key), title };
}

export function numberCitations(
  text: string,
  ledger: Source[],
  resolved: Resolved = {},
): { markdown: string; refs: Reference[] } {
  const byKey = new Map(ledger.map((s) => [s.key, s]));
  const byCanon = new Map(ledger.filter((s) => s.key.startsWith("url:")).map((s) => [canon(s.key.slice(4)), s]));
  const refs: Reference[] = [];
  const index = new Map<string, number>();

  // A DOI that belongs to a PMID we already know is the same paper: one reference, not two.
  const alias = new Map<string, string>();
  for (const [k, v] of Object.entries(resolved)) if (k.startsWith("pmid:") && v.doi) alias.set(`doi:${v.doi.toLowerCase()}`, k);
  for (const s of ledger) if (s.key.startsWith("doi:")) {
    const pm = ledger.find((x) => x.key.startsWith("pmid:") && resolved[x.key]?.doi?.toLowerCase() === s.key.slice(4).toLowerCase());
    if (pm) alias.set(s.key.toLowerCase(), pm.key);
  }

  const marker = (rawKey: string, rawLabel: string): string => {
    let key = alias.get(rawKey.toLowerCase()) ?? rawKey;
    const hit = byKey.get(key) ?? (key.startsWith("url:") ? byCanon.get(canon(key.slice(4))) : undefined);
    if (hit) key = hit.key; // the same page written another way is the same source
    const label = key === rawKey ? rawLabel : `PMID ${key.slice(5)}`;
    let n = index.get(key);
    if (n === undefined) {
      const s = byKey.get(key);
      n = refs.length + 1;
      index.set(key, n);
      const r = resolved[key];
      const exists = !!r && (key.startsWith("url:") ? r.ok === true : true);
      refs.push(
        s
          ? { n, key, kind: s.kind, verified: true, label: s.label, href: s.href, title: s.title }
          : exists
            ? weakRef(n, key, label, r?.title)
            : { n, key, kind: key.startsWith("url:") ? "web" : "paper", verified: false, label, href: undefined },
      );
    }
    const ref = refs[n - 1];
    const tip = (ref.title ?? ref.label).replace(/"/g, "'");
    if (ref.verified) return `[\\[${n}\\]](${ref.href} "${tip}")`;
    if (ref.weak) return `[\\[${n}\\]](${ref.href} "${tip} (${tr("not in this run's tool output, but confirmed to exist")})")`;
    return `[\\[${n}?\\]](#unverified "${tr("Could not verify: this source is not in the tool output")}")`;
  };

  // Models often write [PMID: 123](https://pubmed...) themselves. Turn links to a known source back into the bare
  // address so they are numbered and checked like every other mention; ordinary links stay as they are.
  const cut = text.search(/\n\n> ⚠/); // the notes the server appends under the answer are left as they are
  const head = cut >= 0 ? text.slice(0, cut) : text;
  const tail = cut >= 0 ? text.slice(cut) : "";
  const flat = head.replace(/\[([^\]]*)\]\((https?:\/\/[^)\s]+)\)/g, (m, label: string, url: string) => {
    const pm = /pubmed\.ncbi\.nlm\.nih\.gov\/(\d{4,9})/.exec(url);
    if (pm) return `PMID ${pm[1]}`;
    const doi = /doi\.org\/(10\.\d{4,9}\/\S+)/.exec(url);
    if (doi) return doi[1];
    if (/^\s*(PMID|DOI)\b/i.test(label) || byKey.has(`url:${nu(url)}`) || byCanon.has(canon(url))) return nu(url);
    return m;
  });

  const markdown = flat
    .split(/(```[\s\S]*?```|`[^`\n]+`|\[[^\]]*\]\([^)]*\))/g)
    .map((part, i) => {
      if (i % 2 === 1) return part;
      return part.replace(TOKEN_RE, (m, pmid: string | undefined, doi: string | undefined, url: string | undefined) => {
        if (pmid) return marker(`pmid:${pmid}`, `PMID ${pmid}`);
        if (doi) {
          const d = trimEnd(doi);
          return marker(`doi:${d}`, `DOI ${d}`) + doi.slice(d.length);
        }
        const u = nu(trimEnd(url as string));
        const tail = (url as string).slice(trimEnd(url as string).length);
        // The same paper often appears as a PMID in one place and as its PubMed / doi.org address in another.
        const pm = /pubmed\.ncbi\.nlm\.nih\.gov\/(\d{4,9})/.exec(u);
        if (pm) return marker(`pmid:${pm[1]}`, `PMID ${pm[1]}`) + tail;
        const dm = /(?:dx\.)?doi\.org\/(10\.\d{4,9}\/\S+)/.exec(u);
        if (dm) return marker(`doi:${dm[1]}`, `DOI ${dm[1]}`) + tail;
        return marker(`url:${u}`, u) + tail;
      });
    })
    .join("")
    // tidy what is left around removed tokens: empty brackets and spaces before punctuation
    .replace(/[（(]\s*[;；,，]?\s*[)）]/g, "")
    .replace(/\s+([。，；.,;])/g, "$1")
    // The same source named twice in a row (PMID, then its URL, then its DOI) is one chip, not three.
    .replace(/(\[\\\[(\d+)\\\]\]\([^)]*\))(?:\s*[;；,，]?\s*\[\\\[\2\\\]\]\([^)]*\))+/g, "$1")
    .replace(/[（(]\s*[;；,，]?\s*[)）]/g, "");

  return { markdown: markdown + tail, refs };
}
