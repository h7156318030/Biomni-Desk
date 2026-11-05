"""Tested analysis helpers that the built-in skills call, so the agent does not improvise statistics from scratch.

Every function reads files from the working directory, writes its tables/figures there with a stated prefix, and prints a
short summary with the file names. They fail with a plain message instead of a traceback when the input has the wrong shape.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def _plt():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    return plt


def _read_table(path: str) -> pd.DataFrame:
    sep = "\t" if str(path).lower().endswith((".tsv", ".txt")) else ","
    return pd.read_csv(path, sep=sep, index_col=0)


# ---- bulk RNA-seq differential expression (PyDESeq2) --------------------------------------------------------------

def de_deseq2(counts: str, metadata: str, condition: str, treat: str, ref: str, out: str = "deseq2", min_total_count: int = 10, alpha: float = 0.05) -> str:
    """DESeq2-style differential expression on RAW integer counts. `counts`: genes x samples (or samples x genes) table;
    `metadata`: one row per sample with a `condition` column. Writes <out>_results.csv and <out>_volcano.png."""
    from pydeseq2.dds import DeseqDataSet
    from pydeseq2.ds import DeseqStats

    cm, md = _read_table(counts), _read_table(metadata)
    if condition not in md.columns:
        return f"The metadata has no column {condition}; columns present: {list(md.columns)}"
    if set(md.index) <= set(cm.columns):  # genes x samples -> samples x genes
        cm = cm.T
    if not set(md.index) <= set(cm.index):
        return "Sample names do not match: the count table and the metadata share no sample names."
    cm = cm.loc[md.index]
    if (cm.values < 0).any() or not np.allclose(cm.values, np.round(cm.values)):
        return "The count table has negative or fractional values: DESeq2 needs raw integer counts, not TPM, FPKM or normalised values."
    cm = cm.round().astype(int)
    cm = cm.loc[:, cm.sum(axis=0) >= min_total_count]
    md = md[[condition]].copy()
    levels = set(md[condition])
    if treat not in levels or ref not in levels:
        return f"{condition} has no level {treat} or {ref}; levels present: {sorted(levels)}"
    n_t, n_r = int((md[condition] == treat).sum()), int((md[condition] == ref).sum())
    if min(n_t, n_r) < 2:
        return f"Each group needs at least 2 replicates to estimate dispersion ({treat}={n_t}, {ref}={n_r})."
    # n_cpus=1: pydeseq2 otherwise starts joblib worker processes, which fail intermittently on Windows
    dds = DeseqDataSet(counts=cm, metadata=md, design=f"~{condition}", quiet=True, n_cpus=1)
    dds.deseq2()
    stats = DeseqStats(dds, contrast=[condition, treat, ref], alpha=alpha, quiet=True)
    stats.summary()
    res = stats.results_df.sort_values("padj")
    res.to_csv(f"{out}_results.csv")
    sig = res[(res["padj"] < alpha) & (res["log2FoldChange"].abs() > 1)]
    plt = _plt()
    fig, ax = plt.subplots(figsize=(6, 5), dpi=140)
    ax.scatter(res["log2FoldChange"], -np.log10(res["padj"].clip(lower=1e-300)), s=6, c="#b8b4a6")
    ax.scatter(sig["log2FoldChange"], -np.log10(sig["padj"].clip(lower=1e-300)), s=8, c="#b4552b")
    ax.axhline(-math.log10(alpha), ls="--", lw=0.8, c="#6a6555")
    ax.set_xlabel(f"log2 fold change ({treat} vs {ref})")
    ax.set_ylabel("-log10 adjusted P value")
    ax.set_title(f"Differential expression: {len(sig)} genes, padj<{alpha} and |log2FC|>1")
    fig.tight_layout()
    fig.savefig(f"{out}_volcano.png")
    plt.close(fig)
    top = res.head(10)[["log2FoldChange", "padj"]]
    return (f"DESeq2: {treat} (n={n_t}) vs {ref} (n={n_r}), testing {res['padj'].notna().sum()} genes; {len(sig)} have padj<{alpha} and |log2FC|>1"
            f"(up {(sig['log2FoldChange'] > 0).sum()}, down {(sig['log2FoldChange'] < 0).sum()}).\nTop 10 genes:\n{top.to_string(float_format=lambda v: f'{v:.3g}')}\n"
            f"saved: {out}_results.csv, {out}_volcano.png")


# ---- enrichment --------------------------------------------------------------------------------------------------

def enrich_genes(genes: list[str] | str, library: str = "GO_Biological_Process_2023", out: str = "enrichment", top: int = 15) -> str:
    """Over-representation analysis of a gene list with Enrichr (needs internet). Writes <out>_table.csv and <out>_bar.png."""
    import gseapy as gp

    gl = [g.strip() for g in (genes.replace(",", " ").split() if isinstance(genes, str) else genes) if g.strip()]
    if len(gl) < 5:
        return "Too few genes to be meaningful (at least 5 needed)."
    try:
        enr = gp.enrichr(gene_list=gl, gene_sets=library, organism="human", outdir=None)
    except Exception as e:
        return f"Enrichr query failed: {type(e).__name__}: {str(e)[:120]}"
    res = enr.results.sort_values("Adjusted P-value")
    res.to_csv(f"{out}_table.csv", index=False)
    sig = res[res["Adjusted P-value"] < 0.05]
    plt = _plt()
    show = res.head(top).iloc[::-1]
    fig, ax = plt.subplots(figsize=(7.5, 0.4 * len(show) + 1.5), dpi=140)
    ax.barh(show["Term"].str[:60], -np.log10(show["Adjusted P-value"].clip(lower=1e-300)), color="#2b6b5a")
    ax.set_xlabel("-log10 adjusted P value")
    ax.set_title(f"{library}: {len(gl)} input genes, {len(sig)} terms at FDR<0.05")
    fig.tight_layout()
    fig.savefig(f"{out}_bar.png")
    plt.close(fig)
    lines = [f"{r['Term'][:70]} | FDR {r['Adjusted P-value']:.2g} | overlap {r['Overlap']} | {str(r['Genes'])[:60]}" for _, r in res.head(10).iterrows()]
    return f"Enrichr ({library}): {len(gl)} input genes, {len(sig)} terms at FDR<0.05. Top 10:\n" + "\n".join(lines) + f"\nsaved: {out}_table.csv, {out}_bar.png"


# ---- survival ----------------------------------------------------------------------------------------------------

def survival_km_cox(table: str, time: str, event: str, group: str = "", covariates: list[str] | None = None, out: str = "survival") -> str:
    """Kaplan-Meier + log-rank by `group`, and a Cox model with `covariates` (+ group). `event` is 1 = event, 0 = censored."""
    from lifelines import CoxPHFitter, KaplanMeierFitter
    from lifelines.statistics import logrank_test, multivariate_logrank_test

    df = pd.read_csv(table, sep="\t" if table.lower().endswith((".tsv", ".txt")) else ",")
    for c in (time, event) + ((group,) if group else ()):
        if c not in df.columns:
            return f"the table has no column {c}; columns present: {list(df.columns)}"
    df = df.dropna(subset=[time, event])
    if not set(df[event].unique()) <= {0, 1}:
        return f"The {event} column must be 0/1 (1 = event, 0 = censored); it currently holds {sorted(df[event].unique())[:6]}"
    lines = [f"Survival analysis: {len(df)} patients, {int(df[event].sum())} events, median follow-up {df[time].median():.3g}."]
    plt = _plt()
    fig, ax = plt.subplots(figsize=(6, 4.5), dpi=140)
    kmf = KaplanMeierFitter()
    if group:
        groups = [g for g, d in df.groupby(group) if len(d) >= 2]
        for g in groups:
            d = df[df[group] == g]
            kmf.fit(d[time], d[event], label=f"{g} (n={len(d)})")
            kmf.plot_survival_function(ax=ax, ci_show=True)
            m = kmf.median_survival_time_
            lines.append(f"  {g}: n={len(d)}, events {int(d[event].sum())}, median survival {'not reached' if np.isinf(m) else f'{m:.3g}'}")
        if len(groups) == 2:
            a, b = (df[df[group] == g] for g in groups)
            p = logrank_test(a[time], b[time], a[event], b[event]).p_value
        elif len(groups) > 2:
            p = multivariate_logrank_test(df[time], df[group], df[event]).p_value
        else:
            p = float("nan")
        lines.append(f"  log-rank P = {p:.3g}")
        ax.set_title(f"Kaplan-Meier (log-rank P={p:.3g})")
    else:
        kmf.fit(df[time], df[event])
        kmf.plot_survival_function(ax=ax)
        ax.set_title("Kaplan-Meier")
    ax.set_xlabel(time)
    ax.set_ylabel("survival probability")
    fig.tight_layout()
    fig.savefig(f"{out}_km.png")
    plt.close(fig)
    cols = list(covariates or []) + ([group] if group and group not in (covariates or []) else [])
    if cols:
        cox_df = pd.get_dummies(df[[time, event] + cols], columns=[c for c in cols if df[c].dtype == object], drop_first=True).dropna().astype(float)
        cph = CoxPHFitter(penalizer=0.01).fit(cox_df, duration_col=time, event_col=event)
        s = cph.summary[["exp(coef)", "exp(coef) lower 95%", "exp(coef) upper 95%", "p"]]
        s.to_csv(f"{out}_cox.csv")
        lines.append("Cox proportional hazards (HR [95% CI], P):\n" + "\n".join(f"  {i}: {r['exp(coef)']:.3g} [{r['exp(coef) lower 95%']:.3g}, {r['exp(coef) upper 95%']:.3g}], P={r['p']:.3g}" for i, r in s.iterrows()))
    lines.append(f"saved: {out}_km.png" + (f", {out}_cox.csv" if cols else ""))
    return "\n".join(lines)


# ---- small-molecule properties ----------------------------------------------------------------------------------

def molecule_properties(smiles: list[str] | str, out: str = "molecules") -> str:
    """RDKit physicochemical properties, Lipinski/Veber rules, QED and PAINS alerts for SMILES (a list, or a CSV with a `smiles` column)."""
    from rdkit import Chem
    from rdkit.Chem import Crippen, Descriptors, Lipinski, QED, rdMolDescriptors
    from rdkit.Chem.FilterCatalog import FilterCatalog, FilterCatalogParams

    if isinstance(smiles, str):
        smiles = list(pd.read_csv(smiles)["smiles"]) if smiles.lower().endswith(".csv") else smiles.split()
    params = FilterCatalogParams()
    params.AddCatalog(FilterCatalogParams.FilterCatalogs.PAINS)
    pains = FilterCatalog(params)
    rows = []
    for s in smiles:
        m = Chem.MolFromSmiles(s)
        if m is None:
            rows.append({"smiles": s, "valid": False})
            continue
        mw, logp, hbd, hba = Descriptors.MolWt(m), Crippen.MolLogP(m), Lipinski.NumHDonors(m), Lipinski.NumHAcceptors(m)
        tpsa, rot = rdMolDescriptors.CalcTPSA(m), rdMolDescriptors.CalcNumRotatableBonds(m)
        viol = sum([mw > 500, logp > 5, hbd > 5, hba > 10])
        entry = pains.GetFirstMatch(m)
        rows.append({"smiles": s, "valid": True, "MW": round(mw, 1), "logP": round(logp, 2), "HBD": hbd, "HBA": hba, "TPSA": round(tpsa, 1), "RotB": rot,
                     "QED": round(QED.qed(m), 3), "Lipinski violations": viol, "Veber pass": bool(tpsa <= 140 and rot <= 10), "PAINS": entry.GetDescription() if entry else ""})
    df = pd.DataFrame(rows)
    df.to_csv(f"{out}.csv", index=False)
    ok = df[df["valid"]]
    return (f"{len(df)} molecules, {len(ok)} valid. Lipinski 0 violations: {int((ok['Lipinski violations'] == 0).sum())}; Veber pass: {int(ok['Veber pass'].sum())}; PAINS alerts: {int((ok['PAINS'] != '').sum())}."
            f"These are rule-of-thumb filters, not ADMET predictions.\n{ok.drop(columns=['valid']).head(12).to_string(index=False)}\nsaved: {out}.csv")


# ---- PCR primers ------------------------------------------------------------------------------------------------

def design_primers(sequence: str, target_start: int = -1, target_len: int = 0, product_min: int = 100, product_max: int = 300, n: int = 3) -> str:
    """Primer3 PCR primer pairs for a DNA sequence (optionally flanking a target region, 0-based start and length)."""
    import primer3

    seq = "".join(c for c in sequence.upper() if c in "ACGTN")
    if len(seq) < product_min + 20:
        return f"The sequence is too short ({len(seq)} nt); at least {product_min + 20} nt are needed."
    args: dict[str, Any] = {"SEQUENCE_ID": "q", "SEQUENCE_TEMPLATE": seq}
    if target_start >= 0 and target_len > 0:
        args["SEQUENCE_TARGET"] = [target_start, target_len]
    res = primer3.bindings.design_primers(args, {"PRIMER_OPT_SIZE": 20, "PRIMER_MIN_SIZE": 18, "PRIMER_MAX_SIZE": 25, "PRIMER_OPT_TM": 60.0, "PRIMER_MIN_TM": 57.0,
                                                 "PRIMER_MAX_TM": 63.0, "PRIMER_MIN_GC": 40.0, "PRIMER_MAX_GC": 60.0, "PRIMER_PRODUCT_SIZE_RANGE": [[product_min, product_max]],
                                                 "PRIMER_NUM_RETURN": n})
    k = res.get("PRIMER_PAIR_NUM_RETURNED", 0)
    if not k:
        return "No acceptable primer pair was found: " + str(res.get("PRIMER_PAIR_EXPLAIN", ""))[:200]
    lines = [f"Primer3 found {k} pairs (Tm 57–63 °C, GC 40–60%, product {product_min}–{product_max} bp). Check the primers' specificity with BLAST/Primer-BLAST before use:"]
    for i in range(k):
        lines.append(f"pair {i + 1}: F {res[f'PRIMER_LEFT_{i}_SEQUENCE']} (Tm {res[f'PRIMER_LEFT_{i}_TM']:.1f}, GC {res[f'PRIMER_LEFT_{i}_GC_PERCENT']:.0f}%)  "
                     f"R {res[f'PRIMER_RIGHT_{i}_SEQUENCE']} (Tm {res[f'PRIMER_RIGHT_{i}_TM']:.1f}, GC {res[f'PRIMER_RIGHT_{i}_GC_PERCENT']:.0f}%)  product {res[f'PRIMER_PAIR_{i}_PRODUCT_SIZE']} bp")
    return "\n".join(lines)


# ---- power and sample size --------------------------------------------------------------------------------------

def power_sample_size(kind: str, effect: float, alpha: float = 0.05, power: float = 0.8, p0: float = 0.0, ratio: float = 1.0) -> str:
    """Sample size per group. kind='ttest' (effect = Cohen's d), 'proportion' (effect = p1, p0 = p2), 'survival' (effect = hazard ratio; returns events and total n at event rate p0)."""
    from statsmodels.stats.power import NormalIndPower, TTestIndPower
    from statsmodels.stats.proportion import proportion_effectsize

    if kind == "ttest":
        n = TTestIndPower().solve_power(effect_size=effect, alpha=alpha, power=power, ratio=ratio)
        return f"Two-sample t-test: d={effect}, α={alpha}, power={power}: at least {math.ceil(n)} per group ({math.ceil(n) + math.ceil(n * ratio)} in all)."
    if kind == "proportion":
        h = proportion_effectsize(effect, p0)
        n = NormalIndPower().solve_power(effect_size=h, alpha=alpha, power=power, ratio=ratio)
        return f"Two-proportion comparison: {effect:.3g} vs {p0:.3g}, α={alpha}, power={power}: at least {math.ceil(n)} per group."
    if kind == "survival":
        from scipy.stats import norm

        za, zb = norm.ppf(1 - alpha / 2), norm.ppf(power)
        d = (za + zb) ** 2 * (1 + ratio) ** 2 / (ratio * math.log(effect) ** 2)
        total = math.ceil(d / p0) if p0 else None
        return f"Survival endpoint (Schoenfeld): HR={effect}, α={alpha} (two-sided), power={power}: {math.ceil(d)} events needed" + (f"; with an event rate of {p0:.0%}, about {total} patients in total." if total else ".")
    return "kind must be ttest, proportion or survival"


# ---- meta-analysis ----------------------------------------------------------------------------------------------

def meta_analysis(table: str, effect: str = "effect", se: str = "se", label: str = "study", out: str = "meta", ratio_scale: bool = False) -> str:
    """Fixed- and random-effects (DerSimonian-Laird) pooling from a table with one effect and standard error per study.
    Set ratio_scale=True when effects are log odds/risk/hazard ratios (the report also gives the exponentiated values)."""
    df = pd.read_csv(table)
    for c in (effect, se):
        if c not in df.columns:
            return f"the table has no column {c}; columns present: {list(df.columns)}"
    y, s = df[effect].astype(float).to_numpy(), df[se].astype(float).to_numpy()
    if len(y) < 2 or (s <= 0).any():
        return "At least 2 studies are needed, and the standard errors must be > 0."
    w = 1 / s**2
    fixed = (w * y).sum() / w.sum()
    q = (w * (y - fixed) ** 2).sum()
    dfree = len(y) - 1
    c = w.sum() - (w**2).sum() / w.sum()
    tau2 = max(0.0, (q - dfree) / c)
    wr = 1 / (s**2 + tau2)
    rand = (wr * y).sum() / wr.sum()
    se_r, se_f = math.sqrt(1 / wr.sum()), math.sqrt(1 / w.sum())
    i2 = max(0.0, (q - dfree) / q) * 100 if q > 0 else 0.0
    from scipy.stats import chi2, norm

    p_q = 1 - chi2.cdf(q, dfree)
    f = (lambda v: math.exp(v)) if ratio_scale else (lambda v: v)
    plt = _plt()
    fig, ax = plt.subplots(figsize=(6.5, 0.45 * len(y) + 2), dpi=140)
    names = df[label].astype(str).tolist() if label in df.columns else [f"study {i + 1}" for i in range(len(y))]
    for i, (yy, ss) in enumerate(zip(y, s)):
        ax.plot([f(yy - 1.96 * ss), f(yy + 1.96 * ss)], [len(y) - i] * 2, c="#2b6b5a")
        ax.plot(f(yy), len(y) - i, "s", c="#2b6b5a")
    ax.plot([f(rand - 1.96 * se_r), f(rand + 1.96 * se_r)], [0] * 2, c="#b4552b", lw=3)
    ax.plot(f(rand), 0, "D", c="#b4552b")
    ax.axvline(1 if ratio_scale else 0, ls="--", c="#6a6555", lw=0.8)
    ax.set_yticks(list(range(len(y), 0, -1)) + [0])
    ax.set_yticklabels(names + ["random-effects pooled"])
    ax.set_title(f"Forest plot (I²={i2:.0f}%)")
    fig.tight_layout()
    fig.savefig(f"{out}_forest.png")
    plt.close(fig)
    z = rand / se_r
    return (f"{len(y)} studies. Fixed effect: {f(fixed):.3g} [{f(fixed - 1.96 * se_f):.3g}, {f(fixed + 1.96 * se_f):.3g}]; "
            f"Random effects (DL): {f(rand):.3g} [{f(rand - 1.96 * se_r):.3g}, {f(rand + 1.96 * se_r):.3g}], P={2 * (1 - norm.cdf(abs(z))):.3g}. "
            f"Heterogeneity: Q={q:.2f} (P={p_q:.3g}), I²={i2:.0f}%, τ²={tau2:.3g}. saved: {out}_forest.png."
            f"{'I² is high; the random-effects result is more credible, and the sources of heterogeneity should be explored.' if i2 > 50 else ''}")


# ---- single-cell RNA-seq (Scanpy) -------------------------------------------------------------------------------

def scrna_basic(path: str, out: str = "scrna", min_genes: int = 200, min_cells: int = 3, max_mito: float = 20.0, resolution: float = 0.8) -> str:
    """Standard Scanpy workflow on raw counts (.h5ad, .h5 or a 10x folder): QC, normalise, HVGs, PCA, neighbours, UMAP, Leiden, marker genes."""
    import scanpy as sc

    p = Path(path)
    adata = sc.read_h5ad(p) if p.suffix == ".h5ad" else (sc.read_10x_h5(p) if p.suffix == ".h5" else sc.read_10x_mtx(p))
    adata.var_names_make_unique()
    n0 = adata.n_obs
    adata.var["mt"] = adata.var_names.str.upper().str.startswith("MT-")
    sc.pp.calculate_qc_metrics(adata, qc_vars=["mt"], inplace=True, percent_top=None, log1p=False)
    sc.pp.filter_cells(adata, min_genes=min_genes)
    sc.pp.filter_genes(adata, min_cells=min_cells)
    if adata.var["mt"].any():
        adata = adata[adata.obs["pct_counts_mt"] < max_mito].copy()
    if adata.n_obs < 50:
        return f"Only {adata.n_obs} cells remain after QC (from {n0}); relax the thresholds or check whether the data are raw counts."
    adata.layers["counts"] = adata.X.copy()
    sc.pp.normalize_total(adata, target_sum=1e4)
    sc.pp.log1p(adata)
    sc.pp.highly_variable_genes(adata, n_top_genes=min(2000, adata.n_vars), flavor="seurat")
    sc.pp.pca(adata, n_comps=min(30, adata.n_obs - 1, adata.n_vars - 1), use_highly_variable=True)
    sc.pp.neighbors(adata, n_neighbors=15, n_pcs=min(20, adata.obsm["X_pca"].shape[1]))
    sc.tl.umap(adata)
    try:
        sc.tl.leiden(adata, resolution=resolution, flavor="igraph", n_iterations=2, directed=False)
    except Exception:
        from sklearn.cluster import KMeans

        adata.obs["leiden"] = pd.Categorical(KMeans(n_clusters=8, n_init=5, random_state=0).fit_predict(adata.obsm["X_pca"]).astype(str))
    sc.tl.rank_genes_groups(adata, "leiden", method="wilcoxon")
    plt = _plt()
    fig = sc.pl.umap(adata, color="leiden", show=False, return_fig=True)
    fig.savefig(f"{out}_umap.png", dpi=140, bbox_inches="tight")
    plt.close("all")
    markers = sc.get.rank_genes_groups_df(adata, None)
    markers = markers[markers["pvals_adj"] < 0.05].groupby("group", observed=True).head(5)
    markers.to_csv(f"{out}_markers.csv", index=False)
    adata.write_h5ad(f"{out}.h5ad")
    sizes = adata.obs["leiden"].value_counts().sort_index()
    top = {g: ", ".join(d["names"].head(4)) for g, d in markers.groupby("group", observed=True)}
    return (f"Scanpy: {n0} → after QC {adata.n_obs} cells, {adata.n_vars} genes, {len(sizes)} clusters (Leiden, resolution {resolution}).\n"
            + "\n".join(f"  cluster {g}: {n} cells; marker gene {top.get(g, '—')}" for g, n in sizes.items())
            + f"\nsaved: {out}_umap.png, {out}_markers.csv, {out}.h5ad. Cell-type annotation needs marker genes and the literature; the program does not annotate automatically.")


# ---- microplate layout ------------------------------------------------------------------------------------------

def plate_layout(samples: list[str], replicates: int = 3, controls: list[str] | None = None, rows: int = 8, cols: int = 12, out: str = "plate", seed: int = 1) -> str:
    """Randomised 96/384-well layout: edge wells left as buffer, controls spread out, replicates scattered. Writes <out>.csv."""
    rng = np.random.default_rng(seed)
    ctrl = controls or ["negative control", "positive control"]
    inner = [(r, c) for r in range(1, rows - 1) for c in range(1, cols - 1)]
    items = [s for s in samples for _ in range(replicates)] + [c for c in ctrl for _ in range(replicates)]
    if len(items) > len(inner):
        return f"{len(items)} wells are needed, but only {len(inner)} inner wells remain after excluding the edge; reduce the samples or replicates."
    order = rng.permutation(len(inner))[: len(items)]
    grid = [["" for _ in range(cols)] for _ in range(rows)]
    recs = []
    for item, k in zip(items, order):
        r, c = inner[k]
        well = f"{chr(65 + r)}{c + 1}"
        grid[r][c] = item
        recs.append({"well": well, "item": item})
    pd.DataFrame(grid, index=[chr(65 + i) for i in range(rows)], columns=range(1, cols + 1)).to_csv(f"{out}.csv")
    return f"Laid out {len(items)} wells ({len(samples)} samples + {len(ctrl)} controls, {replicates} replicates each); edge wells are kept as a buffer (to reduce edge effects); random seed {seed}. saved: {out}.csv"
