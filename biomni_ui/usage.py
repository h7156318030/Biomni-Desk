"""How often each tool, skill and Biomni function has been used: counts only, no content.

Used to put the common ways first when the agent searches for a skill or a function. The file is ui_data/usage.json (a test run can point it
elsewhere with BIOMNI_UI_USAGE_FILE)."""

from __future__ import annotations

import json
import math
import os
import threading
from pathlib import Path
from typing import Any

_DEFAULT = Path(__file__).resolve().parent.parent / "ui_data" / "usage.json"


class UsageStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self._counts: dict[str, int] = self._load()

    def _load(self) -> dict[str, int]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return {str(k): int(v) for k, v in data.items()} if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._counts, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError:
            pass  # counting is an aid: a failed write must not stop the task

    def bump(self, kind: str, name: str, n: int = 1) -> None:
        name = str(name or "").strip()
        if not name:
            return
        key = f"{kind}:{name}"
        with self._lock:
            self._counts[key] = self._counts.get(key, 0) + n
            self._save()

    def count(self, kind: str, name: str) -> int:
        return self._counts.get(f"{kind}:{name}", 0)

    def bonus(self, kind: str, name: str) -> float:
        """A small score for ranking: 0 for never used, rising slowly with use (capped at 2)."""
        return min(2.0, math.log1p(self.count(kind, name)))

    def top(self, kind: str, limit: int = 10) -> list[dict[str, Any]]:
        prefix = f"{kind}:"
        rows = [(k[len(prefix):], v) for k, v in self._counts.items() if k.startswith(prefix)]
        rows.sort(key=lambda x: (-x[1], x[0]))
        return [{"name": n, "count": c} for n, c in rows[:limit]]


_STORE: UsageStore | None = None


def store() -> UsageStore:
    """The one store of this process (created on first use, so a test can point it elsewhere first)."""
    global _STORE
    if _STORE is None:
        _STORE = UsageStore(os.environ.get("BIOMNI_UI_USAGE_FILE") or _DEFAULT)
    return _STORE
