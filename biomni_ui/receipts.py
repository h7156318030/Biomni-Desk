"""Per-call receipts and a per-task QC summary, kept in the conversation's execution_trace folder.

A receipt records what the agent called (tool name and arguments), what came back (the full result is saved as a file and
hashed with SHA-256), how long it took, which files it changed, and whether the call looks failed.

The QC summary lists the calls that failed and were never followed by a success of the same tool, plus the specifics and
identifiers the answer uses that the tool output does not contain. It is written to disk for review. It is not added to the
answer text: the answer is shown as written.

Nothing here may break a task: callers wrap these functions and continue when they raise.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any

MAX_STORED_BYTES = 20_000_000  # results above this are hashed but not saved in full
ARG_LIMIT = 2000
SUMMARY_LIMIT = 160

# A result counts as failed when it opens with one of these messages (the first 400 characters are checked).
_FAILED = re.compile(
    r"^(No tool named|No such (tool|skill)|Could not (load|read)|Tool \S+ cannot run|Error\b|Traceback \(most recent call last\)|The call failed)",
    re.M,
)

_LOCK = threading.Lock()


def _trace(cwd: str | Path) -> Path:
    d = Path(cwd) / "execution_trace"
    d.mkdir(parents=True, exist_ok=True)
    return d


def looks_failed(result: str) -> bool:
    return bool(_FAILED.search(str(result or "")[:400]))


def record(cwd: str | Path, call_id: str | None, name: str, arguments: Any, result: str, elapsed: float, files: list[str] | None = None) -> dict[str, Any]:
    """Write one receipt for a tool call and return it. The full result is saved next to the receipts log when it is small enough."""
    text = str(result or "")
    raw = text.encode("utf-8", "replace")
    digest = hashlib.sha256(raw).hexdigest()
    rid = f"{time.strftime('%Y%m%dT%H%M%S')}_{re.sub(r'[^A-Za-z0-9_]', '_', name)[:40]}_{uuid.uuid4().hex[:6]}"
    trace = _trace(cwd)
    result_file = None
    if len(raw) <= MAX_STORED_BYTES:
        out = trace / "receipts" / f"{rid}.txt"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(raw)
        result_file = out.relative_to(Path(cwd)).as_posix()
    try:
        args_text = json.dumps(arguments, ensure_ascii=False, sort_keys=True, default=str)
    except (TypeError, ValueError):
        args_text = str(arguments)
    receipt = {
        "id": rid,
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "call_id": call_id,
        "tool": name,
        "arguments": args_text[:ARG_LIMIT],
        "arguments_truncated": len(args_text) > ARG_LIMIT,
        "elapsed_seconds": round(float(elapsed), 2),
        "result_bytes": len(raw),
        "result_sha256": digest,
        "result_file": result_file,
        "summary": " ".join(text.strip().split())[:SUMMARY_LIMIT],
        "failed": looks_failed(text),
        "files": list(files or []),
    }
    with _LOCK, open(trace / "receipts.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(receipt, ensure_ascii=False) + "\n")
    return receipt


def read_all(cwd: str | Path) -> list[dict[str, Any]]:
    path = Path(cwd) / "execution_trace" / "receipts.jsonl"
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue  # a torn line from an interrupted write is skipped, not fatal
    return rows


def count(cwd: str | Path) -> int:
    return len(read_all(cwd))


def verify(cwd: str | Path, receipt: dict[str, Any]) -> bool:
    """True when the saved result file still hashes to the receipt's SHA-256."""
    rel = receipt.get("result_file")
    if not rel:
        return False
    path = Path(cwd) / rel
    return path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == receipt.get("result_sha256")


def qc_summary(receipts: list[dict[str, Any]], unverified: list[str] | None = None, unsupported: list[str] | None = None) -> dict[str, Any]:
    """Blocking items for one task.

    A failed call blocks only when no later call of the same tool succeeded. `unverified` lists specifics the answer uses that the
    tool output does not contain; `unsupported` lists identifiers the answer cites that never appeared in what the agent saw.
    """
    unresolved = []
    for i, r in enumerate(receipts):
        if not r.get("failed"):
            continue
        later_ok = any(s.get("tool") == r.get("tool") and not s.get("failed") for s in receipts[i + 1:])
        if not later_ok:
            unresolved.append({"id": r.get("id"), "tool": r.get("tool"), "reason": r.get("summary", "")})
    unverified = list(unverified or [])
    unsupported = list(unsupported or [])
    return {
        "calls": len(receipts),
        "failed_calls": sum(1 for r in receipts if r.get("failed")),
        "unresolved_failures": unresolved,
        "unverified_specifics": unverified,
        "unsupported_identifiers": unsupported,
        "gate_pass": not unresolved and not unsupported,
    }


def write_qc(cwd: str | Path, summary: dict[str, Any]) -> str:
    """Save the QC summary as qc_<time>.json in the trace folder and return its relative path."""
    path = _trace(cwd) / f"qc_{time.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:6]}.json"
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return path.relative_to(Path(cwd)).as_posix()
