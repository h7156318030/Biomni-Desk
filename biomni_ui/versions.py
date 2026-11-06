"""Versions of the result files a conversation produces, and the provenance of each version (Claude Science's artifact versions).

Each time a step leaves a result file in its conversation folder with new content, the new content is kept as a version:
- the bytes are stored once per content hash, in execution_trace/blobs/ (so a file saved twice with the same content is one blob);
- the version list for each file is in execution_trace/versions.json, with the task that wrote it and the time;
- restoring an older version copies it back as a new version, so history is never rewritten.

Provenance for a version comes from what already exists: the task's question and answer, its code steps, its tool receipts
(execution log), the model and effort it used, and its review, if any. Nothing here calls a model.
"""

from __future__ import annotations

import hashlib
import json
import platform
import shutil
import sys
import threading
import time
from pathlib import Path
from typing import Any

MAX_VERSIONED_BYTES = 50_000_000  # larger files are listed but their versions are not kept
_lock = threading.Lock()


def _trace(conv_dir: Path) -> Path:
    d = Path(conv_dir) / "execution_trace"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _index_path(conv_dir: Path) -> Path:
    return _trace(conv_dir) / "versions.json"


def _read_index(conv_dir: Path) -> dict[str, Any]:
    try:
        return json.loads(_index_path(conv_dir).read_text(encoding="utf-8")).get("files", {})
    except (OSError, ValueError, AttributeError):
        return {}


def _write_index(conv_dir: Path, files: dict[str, Any]) -> None:
    tmp = _index_path(conv_dir).with_suffix(".tmp")
    tmp.write_text(json.dumps({"files": files}, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(_index_path(conv_dir))


def _relative(conv_dir: Path, file_path: Path) -> str | None:
    try:
        return Path(file_path).resolve().relative_to(Path(conv_dir).resolve()).as_posix()
    except ValueError:
        return None  # not inside this conversation's folder: not versioned here


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def record(conv_dir: Path, file_path: Path, task_id: str | None, reason: str = "") -> dict[str, Any] | None:
    """Keep the file's current content as a version when it differs from the latest one. Returns the version, or None if nothing changed."""
    conv_dir = Path(conv_dir)
    rel = _relative(conv_dir, file_path)
    if rel is None or not Path(file_path).is_file():
        return None
    size = Path(file_path).stat().st_size
    if size > MAX_VERSIONED_BYTES:
        return None
    digest = _sha256(file_path)
    with _lock:
        files = _read_index(conv_dir)
        history = files.setdefault(rel, [])
        if history and history[-1]["sha256"] == digest:
            return None
        blob = _trace(conv_dir) / "blobs" / digest
        if not blob.exists():
            blob.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(file_path, blob)
        version = {
            "version": len(history) + 1,
            "sha256": digest,
            "size": size,
            "task_id": task_id or "",
            "time": time.time(),
            "reason": reason,
        }
        history.append(version)
        _write_index(conv_dir, files)
    return version


def versions_of(conv_dir: Path, rel: str) -> list[dict[str, Any]]:
    return list(reversed(_read_index(conv_dir).get(rel, [])))  # newest first


def all_files(conv_dir: Path) -> dict[str, dict[str, Any]]:
    """Each versioned file with its latest version and how many versions it has."""
    out = {}
    for rel, history in _read_index(conv_dir).items():
        if history:
            out[rel] = {"path": rel, "latest": history[-1], "count": len(history)}
    return out


def blob_path(conv_dir: Path, sha256: str) -> Path | None:
    if not sha256 or not all(c in "0123456789abcdef" for c in sha256) or len(sha256) != 64:
        return None
    p = _trace(conv_dir) / "blobs" / sha256
    return p if p.is_file() else None


def restore(conv_dir: Path, rel: str, version_no: int) -> dict[str, Any]:
    """Copy an older version back over the file, recorded as a new version. Raises LookupError if there is no such version."""
    conv_dir = Path(conv_dir)
    history = _read_index(conv_dir).get(rel, [])
    match = next((v for v in history if v["version"] == version_no), None)
    blob = blob_path(conv_dir, match["sha256"]) if match else None
    if match is None or blob is None:
        raise LookupError("No such version")
    target = conv_dir / rel
    shutil.copyfile(blob, target)
    return record(conv_dir, target, None, reason=f"restored from version {version_no}") or {}


def provenance(conv_dir: Path, rel: str, version_no: int, task: dict[str, Any] | None, task_events: list[dict[str, Any]],
               receipts: list[dict[str, Any]]) -> dict[str, Any]:
    """The record of how a version was made. `task` is the task that wrote it (with its prompt), `task_events` its events,
    `receipts` the tool-call receipts made during it. Missing pieces are empty, never invented."""
    history = _read_index(conv_dir).get(rel, [])
    version = next((v for v in history if v["version"] == version_no), None)
    if version is None:
        raise LookupError("No such version")
    model = next((e for e in task_events if e.get("type") == "llm"), {})
    answer = next((e.get("text", "") for e in task_events if e.get("type") == "answer"), "")
    review = next((e.get("text", "") for e in task_events if e.get("type") == "review"), None)
    code = [{"title": e.get("code", "").splitlines()[0][:120] if e.get("code") else "", "language": e.get("language", ""), "code": e.get("code", "")}
            for e in task_events if e.get("type") == "code"]
    return {
        "path": rel,
        "version": version,
        "task": {"id": (task or {}).get("id", version.get("task_id", "")), "prompt": (task or {}).get("prompt", ""), "created": (task or {}).get("created")},
        "messages": {"question": (task or {}).get("prompt", ""), "answer": answer},
        "code": code,
        "execution_log": [{"tool": r.get("tool"), "time": r.get("time"), "summary": r.get("summary", ""), "result_sha256": r.get("result_sha256"),
                           "failed": r.get("failed", False)} for r in receipts],
        "environment": {"python": sys.version.split()[0], "platform": platform.platform(), "model": model.get("model"), "effort": model.get("effort")},
        "review": review,
    }
