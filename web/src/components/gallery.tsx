"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useI18n } from "@/lib/i18n";

type Capability = { area: string; title: string; hint: string; prompt: string };

// Starting points, one per kind of thing the agent can do. They are phrased as ordinary questions.
// Text is English source strings; the gallery translates it when shown and when a prompt is picked.
const CAPABILITIES: Capability[] = [
  { area: "Literature", title: "Find papers by author", hint: "Separates authors who share a name, groups by institution, and lists papers with PMIDs.", prompt: "Find papers by Wei Zhang and separate authors who share the same name" },
  { area: "Literature", title: "Literature review on a topic", hint: "Searches PubMed and summarises the key points, with a source for each claim.", prompt: "Search PubMed for papers from the last two years on APOE4 and Alzheimer's disease, summarise the key points, and include PMIDs" },
  { area: "Protein", title: "Protein quick lookup", hint: "UniProt entry, function, domains and interactions.", prompt: "Look up the UniProt entry for TP53: give the protein name, species and main functions" },
  { area: "Structure", title: "Structures and predictions", hint: "Experimental structures from PDB and predicted structures from AlphaFold.", prompt: "Look up TP53 structure entries in PDB and AlphaFold, and compare their confidence" },
  { area: "Genetics", title: "Variant pathogenicity lookup", hint: "ClinVar clinical significance and gnomAD population frequency.", prompt: "Count pathogenic BRCA1 variants in ClinVar and explain how the count was made" },
  { area: "Genomics", title: "GWAS loci", hint: "Loci associated with a trait in the GWAS Catalog.", prompt: "Find the main loci associated with type 2 diabetes in the GWAS Catalog" },
  { area: "Omics analysis", title: "Pathway enrichment", hint: "GO, KEGG and Reactome enrichment, with FDR reported consistently.", prompt: "Run pathway enrichment on the gene list TP53, MDM2, CDKN1A, BAX, BBC3 and plot the result" },
  { area: "Drugs", title: "Drugs and targets", hint: "Targets, activities and indications from ChEMBL and Open Targets.", prompt: "List the known EGFR inhibitors and indications, and give the source of each activity data point" },
  { area: "Clinical", title: "Clinical trial search", hint: "Ongoing trials from ClinicalTrials.gov.", prompt: "Search ClinicalTrials.gov for ongoing CD19 CAR-T trials and summarise them by status" },
  { area: "Molecular biology", title: "Primer and PCR design", hint: "Design primers, check specificity and annealing temperature.", prompt: "Design a pair of qPCR primers for the GFP gene and give the Tm and amplicon length" },
  { area: "Gene editing", title: "sgRNA design", hint: "CRISPR target selection and off-target risk assessment.", prompt: "Design three SpCas9 sgRNAs for the human MYC gene and assess their off-target risk" },
  { area: "Analysis & plots", title: "Statistics and visualisation", hint: "Runs Python, makes charts and result files.", prompt: "Draw a bar chart with matplotlib: A=3, B=5, C=2; save it as a png and give the path" },
];

const AREAS = [...new Set(CAPABILITIES.map((c) => c.area))];

function shuffled<T>(items: T[]): T[] {
  const a = [...items];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

/** "Explore capabilities": cards with a search box and a shuffle button; a click puts the example in the input. */
export function Gallery({ onPick }: { onPick: (prompt: string) => void }) {
  const { t } = useI18n();
  const [query, setQuery] = useState("");
  const [area, setArea] = useState<string | null>(null);
  const [order, setOrder] = useState<number[]>(() => CAPABILITIES.map((_, i) => i));
  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return order
      .map((i) => CAPABILITIES[i])
      .filter((c) => !area || c.area === area)
      .filter((c) => !q || `${c.area}${c.title}${c.hint}`.toLowerCase().includes(q))
      .slice(0, 6);
  }, [order, query, area]);

  return (
    <section className="mx-auto mt-8 w-full max-w-3xl text-left">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h3 className="text-xs font-medium tracking-wider text-soft">{t("Explore capabilities")}</h3>
        <div className="flex items-center gap-2">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("Search…")}
            className="w-44 rounded-full border border-line bg-card px-3 py-1 text-sm outline-none focus:border-accent"
          />
          <button
            type="button"
            title={t("Shuffle")}
            onClick={() => setOrder(shuffled(CAPABILITIES.map((_, i) => i)))}
            className="grid h-8 w-8 place-items-center rounded-full border border-line bg-card text-soft hover:border-accent"
          >
            ⤮
          </button>
        </div>
      </div>
      <div className="mb-3 flex flex-wrap gap-1.5" role="tablist" aria-label={t("Capability categories")}>
        {[null, ...AREAS].map((a) => (
          <button
            key={a ?? "all"}
            type="button"
            role="tab"
            aria-selected={area === a}
            onClick={() => setArea(a)}
            className={`rounded-full border px-2.5 py-0.5 text-xs ${area === a ? "border-accent bg-accent-soft text-accent" : "border-line text-soft hover:border-accent"}`}
          >
            {a ? t(a) : t("All")}
          </button>
        ))}
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        {shown.map((c) => (
          <button
            key={c.title}
            type="button"
            onClick={() => onPick(t(c.prompt))}
            className="rounded-xl border border-line bg-card p-4 text-left transition hover:border-accent hover:shadow-sm"
          >
            <div className="flex items-center justify-between text-[11px] tracking-wider text-soft">
              <span>{t(c.area)}</span>
              <span className="rounded bg-codebg px-1.5">{t("Skill")}</span>
            </div>
            <div className="mt-1 font-serif text-base font-semibold">{t(c.title)}</div>
            <p className="mt-1 text-xs text-soft">{t(c.hint)}</p>
            <span className="mt-2 block text-xs text-accent">{t("Start →")}</span>
          </button>
        ))}
        {shown.length === 0 && <p className="col-span-full text-sm text-soft">{t("No matching capabilities. Try another keyword.")}</p>}
      </div>
      <Link href="/skills" className="mt-3 inline-block text-sm text-accent hover:underline">
        {t("Browse all skills →")}
      </Link>
    </section>
  );
}
