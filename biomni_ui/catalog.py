"""OpenRouter's public model list: what really exists, what it costs, and which reasoning efforts it accepts.

Used to search for models to add, to refuse names that are not on OpenRouter (or are no longer), and to show only
the effort levels a model really supports. The list needs no key. GPT-family models are left out on purpose: the
only GPT model allowed here is gpt-6-luna through the ChatGPT sign-in.
"""

from __future__ import annotations

import re
import threading
import time
from typing import Any, Callable

import requests

URL = "https://openrouter.ai/api/v1/models"
TTL_SECONDS = 600
GPT_RE = re.compile(r"^openai/|(^|/)gpt-?\d", re.IGNORECASE)
DEFAULT_EFFORTS = ["medium", "high"]


def fetch_models() -> list[dict[str, Any]]:
    try:
        r = requests.get(URL, timeout=20)
    except requests.RequestException:
        with requests.Session() as s:  # some networks fail through the system proxy
            s.trust_env = False
            r = s.get(URL, timeout=20)
    r.raise_for_status()
    return r.json()["data"]


def normalize(m: dict[str, Any]) -> dict[str, Any]:
    pricing = m.get("pricing") or {}
    prompt = float(pricing.get("prompt") or 0) * 1_000_000
    completion = float(pricing.get("completion") or 0) * 1_000_000
    params = m.get("supported_parameters") or []
    reasoning = m.get("reasoning") or {}
    efforts: list[str] = []
    if "reasoning" in params:
        listed = [e for e in (reasoning.get("supported_efforts") or []) if e != "none"]
        efforts = listed or list(DEFAULT_EFFORTS)
    return {
        "id": m["id"],
        "name": m.get("name") or m["id"],
        "context": m.get("context_length") or 0,
        "prompt_per_m": round(prompt, 4),
        "completion_per_m": round(completion, 4),
        "free": m["id"].endswith(":free") or (prompt == 0 and completion == 0),
        "efforts": efforts,
        "default_effort": reasoning.get("default_effort") if reasoning.get("default_effort") in efforts else (efforts[len(efforts) // 2] if efforts else None),
    }


class Catalog:
    """Cached copy of the list. `fetch` is injectable so tests never touch the network."""

    def __init__(self, fetch: Callable[[], list[dict[str, Any]]] = fetch_models, ttl: int = TTL_SECONDS):
        self._fetch = fetch
        self._ttl = ttl
        self._items: dict[str, dict[str, Any]] | None = None
        self._at = 0.0
        self._lock = threading.Lock()

    def _load(self, force: bool = False) -> dict[str, dict[str, Any]] | None:
        with self._lock:
            if self._items is not None and not force and time.time() - self._at < self._ttl:
                return self._items
            try:
                items = {m["id"]: normalize(m) for m in self._fetch() if not GPT_RE.search(m.get("id", ""))}
            except Exception:  # offline: keep serving the old copy if there is one
                return self._items
            self._items, self._at = items, time.time()
            return self._items

    def available(self) -> bool:
        return self._load() is not None

    def get(self, model_id: str) -> dict[str, Any] | None:
        items = self._load()
        return items.get(model_id) if items else None

    def peek(self, model_id: str) -> dict[str, Any] | None:
        """Like `get`, but never goes to the network: only what is already cached."""
        return (self._items or {}).get(model_id)

    def peek_ready(self) -> bool:
        return self._items is not None

    def warm(self) -> None:
        threading.Thread(target=self._load, daemon=True, name="catalog-warm").start()

    def search(self, q: str = "", free_only: bool = False, limit: int = 40) -> list[dict[str, Any]] | None:
        items = self._load()
        if items is None:
            return None
        words = q.lower().split()
        rows = [m for m in items.values() if (not free_only or m["free"]) and all(w in f"{m['id']} {m['name']}".lower() for w in words)]
        # cheap and big-context first when nothing was typed; otherwise best match (shorter id) first
        rows.sort(key=lambda m: (len(m["id"]) if words else 0, not m["free"], m["prompt_per_m"]))
        return rows[:limit]
