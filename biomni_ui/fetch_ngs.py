"""Local, small-scale fetchngs: the run table for a public project or study (ENA), with FASTQ addresses and download commands.

It does not download by default: a project can hold terabytes. The table tells the user what would be fetched and how big it is.
"""

from __future__ import annotations

import re

import requests

from biomni_ui.cache import ttl_cache

ENA_REPORT = "https://www.ebi.ac.uk/ena/portal/api/filereport"
FIELDS = "run_accession,sample_alias,library_layout,library_strategy,base_count,fastq_ftp,fastq_md5"


@ttl_cache(ttl=6 * 3600)
def ena_run_table(accession: str, max_runs: int = 50) -> str:
    """The sequencing runs of a project, study or run accession (PRJ.., SRP.., ERP.., ERR..): sample, layout, size, FASTQ addresses.

    Returns plain text with the table and the curl command for each run; it does not download anything.
    """
    acc = (accession or "").strip()
    if not re.fullmatch(r"(PRJ[EDN][A-Z]\d+|[SEDC]RP\d+|[SEDC]RR\d+|[SEDC]RX\d+|[SEDC]RS\d+|ERR\d+|SRR\d+)", acc):
        return f"Accession format is wrong: {acc}. It should start with PRJ/SRP/ERP/DRP or SRR/ERR/DRR."
    n = max(1, min(int(max_runs or 50), 500))
    try:
        r = requests.get(ENA_REPORT, params={"accession": acc, "result": "read_run", "fields": FIELDS, "format": "tsv"}, timeout=60)
        r.raise_for_status()
    except requests.RequestException as e:
        return f"ENA query failed: {type(e).__name__}: {str(e)[:160]}"
    lines = [ln for ln in r.text.splitlines() if ln.strip()]
    if len(lines) <= 1:
        return f"ENA has no sequencing records for {acc} (or the accession is not public yet)."
    header = lines[0].split("\t")
    rows = [dict(zip(header, ln.split("\t"))) for ln in lines[1:]]
    total_bases = sum(int(x.get("base_count") or 0) for x in rows)
    out = [f"{acc}: {len(rows)} runs, estimated total bases {total_bases / 1e9:.1f} Gb (not downloaded). First {min(n, len(rows))}:"]
    for row in rows[:n]:
        ftp = [f for f in (row.get("fastq_ftp") or "").split(";") if f]
        out.append(f"- {row.get('run_accession')}｜{row.get('sample_alias')}｜{row.get('library_layout')}｜{row.get('library_strategy', '')}｜{int(row.get('base_count') or 0) / 1e9:.2f} Gb")
        for f in ftp:
            out.append(f"  curl -L -C - -o {f.rsplit('/', 1)[-1]} https://{f}")
    out.append("Source: ENA (European Nucleotide Archive) filereport. Check disk space before downloading; for large data, download 1–2 runs first to check.")
    return "\n".join(out)
