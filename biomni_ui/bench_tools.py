"""Tool smoke benchmark: call each live database or tool with a known input and record pass/fail and time.

Run `python -m biomni_ui.bench_tools` to write a report (JSON + text). A failing line is an endpoint or tool that needs a look.
Network-dependent: a failure can mean the outside service is down, not that the tool is wrong.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

CASES = [
    ("uniprot_lookup", {"query": "P01732"}),
    ("clinical_trials", {"condition": "CAR-T"}),
    ("open_targets", {"query": "B-cell acute lymphoblastic leukemia"}),
    ("gnomad_constraint", {"gene": "TP53"}),
    ("gtex_expression", {"gene": "TP53"}),
    ("string_interactions", {"gene": "TP53"}),
    ("reactome_pathways", {"gene_or_term": "TP53"}),
    ("fda_adverse_events", {"drug": "aspirin"}),
    ("geo_search", {"query": "CAR-T"}),
    ("target_tractability", {"gene": "EGFR"}),
    ("civic_gene_variants", {"gene": "EGFR", "max_results": 3}),
    ("ena_run_table", {"accession": "PRJEB1787", "max_runs": 2}),
]
FAIL_WORDS = ("没有返回", "不能运行", "无法加载", "失败", "出错", "报错", "不对", "没有这个工具", "did not return", "cannot run on this computer", "Could not load tool", "failed:", "No tool named", "Wrong arguments")


def run_smoke(out_dir: str = "ui_data/bench") -> list[dict]:
    from biomni_ui import biomni_tools as bt

    rows = []
    for name, args in CASES:
        t0 = time.time()
        out = bt.run_tool(name, args, timeout=120)
        ok = bool(out) and not any(w in out[:200] for w in FAIL_WORDS)
        rows.append({"tool": name, "ok": ok, "seconds": round(time.time() - t0, 1), "head": out[:120].replace("\n", " ")})
    d = Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M")
    (d / f"smoke-{stamp}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [f"{'OK ' if r['ok'] else 'FAIL'} {r['tool']:<24} {r['seconds']:>6}s  {r['head']}" for r in rows]
    (d / f"smoke-{stamp}.txt").write_text("\n".join(lines), encoding="utf-8")
    return rows


if __name__ == "__main__":
    rows = run_smoke()
    print("\n".join(f"{'OK ' if r['ok'] else 'FAIL'} {r['tool']} {r['seconds']}s" for r in rows))
    sys.exit(0 if all(r["ok"] for r in rows) else 1)
