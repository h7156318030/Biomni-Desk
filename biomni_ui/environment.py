"""What this machine can run, measured once at start-up: the Python packages the bio tools use (in the interpreter the Python tool runs
in), and R with the R packages the skill manuals name.

It goes into every task's instructions as plain facts. Without it the model cannot tell an installed tool from a missing one: a manual
that says "R is not installed here" is answered from memory, and a package that is installed is never mentioned. The probe runs in a
background thread, so nothing waits for it; the agent takes about a minute to load anyway.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import threading
from typing import Any

PY_PACKAGES = (
    "scanpy", "anndata", "muon", "squidpy", "decoupler", "celltypist", "harmonypy", "scvi", "pandas", "numpy", "scipy", "sklearn",
    "statsmodels", "gseapy", "pydeseq2", "Bio", "pysam", "lifelines", "rdkit",
)
R_PACKAGES = ("Seurat", "SingleCellExperiment", "DESeq2", "edgeR", "limma", "clusterProfiler")

_lock = threading.Lock()
_state: dict[str, Any] = {"python": None, "r": None}


def probe_python(names: tuple[str, ...] = PY_PACKAGES) -> tuple[list[str], list[str]]:
    """(installed, missing) import names, checked without importing anything."""
    have: list[str] = []
    missing: list[str] = []
    for name in names:
        try:
            ok = importlib.util.find_spec(name) is not None
        except (ImportError, ValueError):
            ok = False
        (have if ok else missing).append(name)
    return have, missing


def probe_r(packages: tuple[str, ...] = R_PACKAGES, timeout: int = 60) -> dict[str, Any]:
    """Whether Rscript runs, and which of the packages load. Never raises: no R is a result, not an error."""
    rscript = shutil.which("Rscript")
    if not rscript:
        return {"available": False, "have": [], "missing": list(packages)}
    quoted = ", ".join(f'"{p}"' for p in packages)
    code = f"pk <- c({quoted}); cat(pk[vapply(pk, requireNamespace, logical(1), quietly = TRUE)], sep = '\n')"
    try:
        out = subprocess.run([rscript, "--vanilla", "-e", code], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        have = [line.strip() for line in out.stdout.splitlines() if line.strip() in packages]
    except (OSError, subprocess.SubprocessError):
        return {"available": False, "have": [], "missing": list(packages)}
    return {"available": True, "have": have, "missing": [p for p in packages if p not in have]}


def _run() -> None:
    py = probe_python()
    r = probe_r()
    with _lock:
        _state["python"], _state["r"] = py, r


def start() -> None:
    """Measure in the background. Idempotent: a second call does nothing."""
    with _lock:
        if _state["python"] is not None or _state.get("started"):
            return
        _state["started"] = True
    threading.Thread(target=_run, daemon=True, name="environment-probe").start()


def line() -> str:
    """The measured facts for the task's instructions, or nothing before the probe has finished."""
    with _lock:
        py, r = _state["python"], _state["r"]
    if py is None or r is None:
        return ""
    have, missing = py
    parts = [f"Python packages (the interpreter used by Python tools): installed {', '.join(have) or 'none'}; not installed {', '.join(missing) or 'none'}."]
    if r["available"]:
        parts.append(f"R installed; R packages installed {', '.join(r['have']) or 'none'}; not installed {', '.join(r['missing']) or 'none'}.")
    else:
        parts.append("R: Rscript is not installed on this computer, so R packages (such as Seurat) are unavailable.")
    return "## This computer's environment (facts checked at start-up)\n" + "\n".join(f"- {p}" for p in parts)
