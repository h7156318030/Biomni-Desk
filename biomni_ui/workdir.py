"""Where a conversation works: one results folder per conversation, with the record of how the results came about.

The official app keeps `results/` for what the user gets, an `execution_trace/` with the notebook of every step and a ledger of
every reference a search returned. Here each conversation gets <workspace>/results/<conversation id>/ as the working folder of
its shell and Python session, so earlier tasks' files (the old CSVs next to the code, say) are not in the way, a result is
named the same way in the step, the answer and the Results panel, and the folder can be opened or zipped as one thing.
"""

from __future__ import annotations

import json
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()


def results_base() -> Path:
    from biomni.config import default_config

    base = Path(default_config.path).resolve() / "results"
    base.mkdir(parents=True, exist_ok=True)
    return base


def conversation_dir(conversation_id: str | None) -> Path:
    name = re.sub(r"[^A-Za-z0-9_-]", "_", conversation_id or "") or "scratch"
    d = results_base() / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def trace_dir(cwd: Path) -> Path:
    d = Path(cwd) / "execution_trace"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------------------------- the notebook

def _lines(text: str) -> list[str]:
    parts = text.split("\n")
    return [p + "\n" for p in parts[:-1]] + ([parts[-1]] if parts[-1] else [])


def _cell_id() -> str:
    return uuid.uuid4().hex[:8]


def _append_cell(cwd: Path, cell: dict[str, Any]) -> None:
    path = trace_dir(cwd) / "trace.ipynb"
    with _LOCK:
        try:
            nb = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            nb = {"cells": [], "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}, "language_info": {"name": "python"}},
                  "nbformat": 4, "nbformat_minor": 5}
        nb["cells"].append(cell)
        path.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")


def add_step(cwd: Path, language: str, title: str, code: str, output: str) -> None:
    """One shell or Python step as a notebook cell (code and what it printed), so the analysis can be replayed from the file alone."""
    try:
        source = ("%%bash\n" if language == "bash" else "") + (f"# {title}\n" if title else "") + code
        _append_cell(cwd, {"cell_type": "code", "execution_count": None, "id": _cell_id(), "metadata": {"title": title, "time": time.strftime("%Y-%m-%d %H:%M:%S")},
                           "outputs": [{"output_type": "stream", "name": "stdout", "text": _lines(output)}] if output else [], "source": _lines(source)})
    except Exception:
        pass  # the record must never break the work


def add_note(cwd: Path, text: str) -> None:
    try:
        _append_cell(cwd, {"cell_type": "markdown", "id": _cell_id(), "metadata": {}, "source": _lines(text)})
    except Exception:
        pass


# ---------------------------------------------------------------------------------------------- the ledgers

def _append_jsonl(cwd: Path, name: str, row: dict[str, Any]) -> None:
    try:
        with _LOCK, open(trace_dir(cwd) / name, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


def add_references(cwd: Path, query: str, results: list[dict[str, Any]]) -> None:
    """Every page a search returned, appended to references.jsonl: the list a citation in the answer can be checked against."""
    for r in results or []:
        _append_jsonl(cwd, "references.jsonl", {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "query": query, "url": r.get("url"), "title": r.get("title"), "domain": r.get("domain")})


def add_event(cwd: Path, event: dict[str, Any]) -> None:
    """The whole session, one event per line (steps, observations, answer), for audit and replay."""
    _append_jsonl(cwd, "transcript.jsonl", event)
