"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { setPrefill } from "@/lib/prefill";
import { useI18n } from "@/lib/i18n";

type Pipeline = { id: string; title: string; summary: string; inputs: string[]; outputs: string[]; docs: string };

// nf-core community pipelines. Names and links are public; the wording here is ours.
// Descriptions are English source strings; the page translates them when shown.
const PIPELINES: Pipeline[] = [
  { id: "fetchngs", title: "fetchngs", summary: "Download sequencing data and metadata from public databases by accession number.", inputs: ["SRA / ENA / DDBJ / GEO accession list"], outputs: ["FASTQ files", "A sample sheet ready for downstream pipelines"], docs: "https://nf-co.re/fetchngs" },
  { id: "rnaseq", title: "rnaseq", summary: "Transcriptome sequencing: alignment, gene and transcript quantification, and full quality control.", inputs: ["FASTQ sample sheet", "Reference genome and annotation"], outputs: ["Gene expression matrix", "BAM", "MultiQC quality report"], docs: "https://nf-co.re/rnaseq" },
  { id: "sarek", title: "sarek", summary: "Germline and somatic variant calling for whole-genome or targeted sequencing.", inputs: ["FASTQ or BAM sample sheet", "Reference genome"], outputs: ["VCF files", "Annotation results", "Quality report"], docs: "https://nf-co.re/sarek" },
  { id: "scrnaseq", title: "scrnaseq", summary: "Processes single-cell transcriptome data such as 10x Genomics.", inputs: ["FASTQ sample sheet", "Reference genome"], outputs: ["Cell × gene matrix", "Quality report"], docs: "https://nf-co.re/scrnaseq" },
  { id: "chipseq", title: "chipseq", summary: "ChIP-seq peak calling and differential binding analysis.", inputs: ["FASTQ sample sheet (with controls)"], outputs: ["Peak files", "Differential binding regions", "Quality report"], docs: "https://nf-co.re/chipseq" },
  { id: "atacseq", title: "atacseq", summary: "ATAC-seq peak calling and differential accessibility analysis.", inputs: ["FASTQ sample sheet"], outputs: ["Peak files", "Differentially accessible regions", "Quality report"], docs: "https://nf-co.re/atacseq" },
  { id: "methylseq", title: "methylseq", summary: "Bisulfite sequencing (methylation) analysis.", inputs: ["FASTQ sample sheet", "Reference genome"], outputs: ["Methylation site table", "Quality report"], docs: "https://nf-co.re/methylseq" },
  { id: "nanoseq", title: "nanoseq", summary: "Demultiplexing, quality control and alignment for Nanopore data.", inputs: ["FASTQ or fast5 sample sheet"], outputs: ["Alignment results", "Quality report"], docs: "https://nf-co.re/nanoseq" },
  { id: "raredisease", title: "raredisease", summary: "Variant calling and ranking for WGS/WES of rare-disease patients.", inputs: ["Family sample sheet", "Reference genome"], outputs: ["Annotated and ranked variant list"], docs: "https://nf-co.re/raredisease" },
  { id: "oncoanalyser", title: "oncoanalyser", summary: "Integrated DNA/RNA analysis and reporting for tumours.", inputs: ["Tumour/normal BAM or FASTQ"], outputs: ["Reports on variants, copy number, fusion genes and more"], docs: "https://nf-co.re/oncoanalyser" },
];

const BUILD = [
  { title: "Start from an analysis", note: "Turn an analysis you have already done, or a notebook, into a reproducible pipeline.", prompt: "Please turn the analysis I just completed into a reproducible Nextflow pipeline: first list the steps, inputs, outputs and dependencies, and write the code only after I confirm." },
  { title: "Create a reusable module", note: "Wrap one tool or analysis step as a module you can reuse.", prompt: "Please wrap the analysis step below as a reusable Nextflow module (process), stating its inputs, outputs and container or environment:" },
  { title: "Check before running", note: "Check the pipeline for problems before running it on a cluster.", prompt: "Before the real run, check my Nextflow pipeline: parameters, resource needs, containers, input files and likely failure points, and suggest changes." },
];

export default function PipelinesPage() {
  const router = useRouter();
  const { t, lang } = useI18n();
  const [open, setOpen] = useState<string>(PIPELINES[0].id);
  const [query, setQuery] = useState("");
  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return PIPELINES.filter((p) => !q || `${p.id}${p.summary}`.toLowerCase().includes(q));
  }, [query]);
  const selected = PIPELINES.find((p) => p.id === open) ?? PIPELINES[0];
  const listSep = lang === "zh" ? "、" : ", ";

  const go = (text: string) => {
    setPrefill(text);
    router.push("/");
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl px-6 py-8">
        <p className="text-[11px] tracking-wider text-soft">{t("Pipeline centre")}</p>
        <h1 className="font-serif text-3xl font-semibold">{t("Pipelines")}</h1>
        <p className="mt-1 text-sm text-soft">
          {t("Turn analyses into reproducible pipelines. Below is the community-maintained nf-core catalogue: pick one and the agent will help you set it up and run it.")}
        </p>
        <p className="mt-3 rounded-lg border border-line bg-card p-3 text-xs text-soft">
          {t("Pipelines here run on your own computer and need Nextflow and Docker (or Conda). The agent checks the environment first; if something is missing it tells you how to install it, and it does not pretend a run has finished.")}
        </p>

        <h2 className="mt-8 font-serif text-lg font-semibold">{t("Build a custom pipeline")}</h2>
        <ul className="mt-2 grid gap-3 sm:grid-cols-3">
          {BUILD.map((b) => (
            <li key={b.title}>
              <button type="button" onClick={() => go(t(b.prompt))} className="h-full w-full rounded-xl border border-line bg-card p-4 text-left hover:border-accent">
                <span className="block font-serif text-base font-semibold">{t(b.title)}</span>
                <span className="mt-1 block text-xs text-soft">{t(b.note)}</span>
                <span className="mt-2 block text-xs text-accent">{t("Back to the workspace with this task →")}</span>
              </button>
            </li>
          ))}
        </ul>

        <div className="mt-8 flex items-end justify-between gap-3">
          <h2 className="font-serif text-lg font-semibold">{t("nf-core pipelines")}</h2>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("Search…")}
            aria-label={t("Search pipelines")}
            className="w-44 rounded-lg border border-line bg-card px-3 py-1.5 text-sm outline-none focus:border-accent"
          />
        </div>
        <div className="mt-3 grid gap-4 md:grid-cols-[16rem_minmax(0,1fr)]">
          <ul className="space-y-1">
            {shown.map((p) => (
              <li key={p.id}>
                <button
                  type="button"
                  aria-pressed={p.id === open}
                  onClick={() => setOpen(p.id)}
                  className={`w-full rounded-lg border px-3 py-2 text-left ${p.id === open ? "border-accent bg-accent-soft" : "border-line bg-card hover:border-accent"}`}
                >
                  <span className="block font-mono text-sm font-medium">{p.title}</span>
                  <span className="line-clamp-2 block text-xs text-soft">{t(p.summary)}</span>
                </button>
              </li>
            ))}
            {shown.length === 0 && <li className="text-sm text-soft">{t("No matching pipelines.")}</li>}
          </ul>
          <article className="rounded-xl border border-line bg-card p-5">
            <h3 className="font-mono text-xl font-semibold">nf-core/{selected.title}</h3>
            <p className="mt-1 text-sm">{t(selected.summary)}</p>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <div>
                <h4 className="text-xs font-medium text-soft">{t("Required inputs")}</h4>
                <ul className="mt-1 list-disc pl-5 text-sm">{selected.inputs.map((i) => <li key={i}>{t(i)}</li>)}</ul>
              </div>
              <div>
                <h4 className="text-xs font-medium text-soft">{t("Outputs")}</h4>
                <ul className="mt-1 list-disc pl-5 text-sm">{selected.outputs.map((i) => <li key={i}>{t(i)}</li>)}</ul>
              </div>
            </div>
            <div className="mt-5 flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() =>
                  go(
                    t(
                      "I want to use the nf-core/{pipeline} pipeline. First check whether Nextflow and Docker (or Conda) are installed on this machine, then ask me for the inputs I need ({inputs}), then give a sample-sheet template and the run command. Do not say it has finished until it has actually run successfully.",
                      { pipeline: selected.title, inputs: selected.inputs.map((i) => t(i)).join(listSep) },
                    ),
                  )
                }
                className="rounded-lg bg-accent px-4 py-2 text-sm text-white dark:text-black"
              >
                {t("Run this pipeline")}
              </button>
              <a href={selected.docs} target="_blank" rel="noreferrer" className="text-sm text-accent underline">
                {t("Pipeline docs ↗")}
              </a>
            </div>
          </article>
        </div>
      </div>
    </div>
  );
}
