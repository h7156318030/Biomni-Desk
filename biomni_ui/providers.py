"""Where models come from: any OpenAI-compatible endpoint (OpenRouter, DeepSeek, Kimi, GLM, Qwen, Ollama, ...).

Each provider is a base URL plus an optional API key. The OpenRouter connection from `.env` is always there as the
built-in one; others are added in settings and stored in `ui_data/providers.json` on this computer. A key is only
ever sent to its own provider; it is never returned to the page (the page only learns whether one is saved).
"""

from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import requests

BUILTIN_ID = "openrouter"

# Starting points for the "add a provider" form. The address is only a suggestion: "test connection" tells you at once
# whether it answers and whether your key is accepted.
PRESETS: list[dict[str, Any]] = [
    {"id": "anthropic", "name": "Anthropic (Claude)", "base_url": "https://api.anthropic.com/v1", "local": False, "note": "Anthropic's official API (OpenAI-compatible mode). Create the key in the Anthropic console."},
    {"id": "openai", "name": "OpenAI (GPT API)", "base_url": "https://api.openai.com/v1", "local": False, "note": "OpenAI's official API. Create the key on the OpenAI platform."},
    {"id": "google", "name": "Google (Gemini)", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "local": False, "note": "Gemini's OpenAI-compatible API. Create the key in Google AI Studio."},
    {"id": "xai", "name": "xAI (Grok)", "base_url": "https://api.x.ai/v1", "local": False, "note": "xAI's official API. Create the key in the xAI console."},
    {"id": "deepseek","name": "DeepSeek", "base_url": "https://api.deepseek.com/v1", "local": False, "note": "DeepSeek's official API"},
    {"id": "moonshot", "name": "Moonshot (Kimi)", "base_url": "https://api.moonshot.cn/v1", "local": False, "note": "Moonshot's official API"},
    {"id": "zhipu", "name": "Zhipu (GLM)", "base_url": "https://open.bigmodel.cn/api/paas/v4", "local": False, "note": "Zhipu's official GLM API"},
    {"id": "dashscope", "name": "Alibaba Cloud Bailian (Qwen)", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "local": False, "note": "Qwen, OpenAI-compatible mode"},
    {"id": "siliconflow", "name": "SiliconFlow", "base_url": "https://api.siliconflow.cn/v1", "local": False, "note": "Aggregator for many open models"},
    {"id": "minimax", "name": "MiniMax", "base_url": "https://api.minimax.chat/v1", "local": False, "note": "MiniMax's official API"},
    {"id": "volcengine", "name": "Volcano Engine Ark (Doubao)", "base_url": "https://ark.cn-beijing.volces.com/api/v3", "local": False, "note": "ByteDance Doubao and similar models"},
    {"id": "groq", "name": "Groq", "base_url": "https://api.groq.com/openai/v1", "local": False, "note": "Low-latency open models"},
    {"id": "together", "name": "Together AI", "base_url": "https://api.together.xyz/v1", "local": False, "note": "Aggregator for open models"},
    {"id": "mistral", "name": "Mistral", "base_url": "https://api.mistral.ai/v1", "local": False, "note": "Mistral's official API"},
    {"id": "ollama", "name": "Ollama (this computer)", "base_url": "http://localhost:11434/v1", "local": True, "note": "Runs on this computer. No key needed, no cost."},
    {"id": "lmstudio", "name": "LM Studio (this computer)", "base_url": "http://localhost:1234/v1", "local": True, "note": "Runs on this computer. No key needed, no cost."},
    {"id": "custom", "name": "Other (enter the address yourself)", "base_url": "", "local": False, "note": "Any service with an OpenAI-compatible API"},
]


def is_local_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in ("localhost", "127.0.0.1", "::1") or host.endswith(".localhost")


def clean_base_url(url: str) -> str:
    url = (url or "").strip().rstrip("/")
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.netloc:
        raise ValueError("The API address must start with http:// or https://, for example https://api.deepseek.com/v1")
    return url


def explain_http(status: int, body: str = "") -> str:
    if status in (401, 403):
        return f"The key is invalid or has no permission (HTTP {status})."
    if status == 404:
        return "Wrong address: this API has no model list (/models). Check the address; it usually ends with /v1."
    if status == 429:
        return "Too many requests, or the quota is used up (HTTP 429)."
    return f"The API returned HTTP {status}: {body[:160]}"


def fetch_model_ids(base_url: str, api_key: str | None, timeout: int = 20) -> list[str]:
    """The model ids a provider offers (the standard `GET {base}/models` of the OpenAI API). Raises RuntimeError."""
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    url = base_url.rstrip("/") + "/models"
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
    except requests.RequestException:
        if is_local_url(base_url):
            raise RuntimeError("Cannot reach this address. Is the local service (Ollama / LM Studio) running?") from None
        try:
            with requests.Session() as s:  # some networks fail through the system proxy
                s.trust_env = False
                r = s.get(url, headers=headers, timeout=timeout)
        except requests.RequestException as e:
            raise RuntimeError(f"Cannot reach this address: {type(e).__name__}") from e
    if r.status_code != 200:
        raise RuntimeError(explain_http(r.status_code, r.text))
    try:
        data = r.json()
    except ValueError as e:
        raise RuntimeError("The API did not return JSON. The address may be wrong.") from e
    rows = data.get("data") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise RuntimeError("The API returned an unrecognised format (not an OpenAI-style model list).")
    return sorted({str(m.get("id") if isinstance(m, dict) else m) for m in rows if (m.get("id") if isinstance(m, dict) else m)})


class ProviderStore:
    def __init__(self, path: Path, env_base_url: Callable[[], str | None] = lambda: None, env_api_key: Callable[[], str | None] = lambda: None):
        self.path = path
        self._env_url, self._env_key = env_base_url, env_api_key
        self._lock = threading.Lock()

    # -- storage ---------------------------------------------------------------------------------------------
    def _read(self) -> list[dict[str, Any]]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            return []
        rows = data.get("providers", []) if isinstance(data, dict) else []
        return [r for r in rows if isinstance(r, dict) and r.get("id") and r.get("base_url")]

    def _write(self, rows: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"providers": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        tmp.replace(self.path)

    def _builtin(self) -> dict[str, Any] | None:
        url, key = self._env_url(), self._env_key()
        if not url:
            return None
        return {"id": BUILTIN_ID, "name": "OpenRouter (from .env)", "base_url": url.rstrip("/"), "api_key": key or "", "local": False, "builtin": True}

    # -- read --------------------------------------------------------------------------------------------------
    def _all(self) -> list[dict[str, Any]]:
        b = self._builtin()
        return ([b] if b else []) + [{**r, "builtin": False, "local": bool(r.get("local"))} for r in self._read()]

    @staticmethod
    def _public(p: dict[str, Any]) -> dict[str, Any]:
        needs_key = not p["local"]
        return {
            "id": p["id"], "name": p["name"], "base_url": p["base_url"], "local": p["local"], "builtin": p["builtin"],
            "has_key": bool(p.get("api_key")), "ready": bool(p.get("api_key")) or not needs_key,
        }

    def list(self) -> list[dict[str, Any]]:
        return [self._public(p) for p in self._all()]

    def get(self, provider_id: str) -> dict[str, Any] | None:
        return next((p for p in self._all() if p["id"] == provider_id), None)

    def credentials(self, provider_id: str) -> tuple[str, str] | None:
        """(base_url, api_key) when the provider can be used (a local one needs no key), else None."""
        p = self.get(provider_id)
        if p is None or (not p["local"] and not p.get("api_key")):
            return None
        return p["base_url"], p.get("api_key") or "not-needed"

    def ready(self, provider_id: str) -> bool:
        return self.credentials(provider_id) is not None

    def any_ready(self) -> bool:
        return any(self.ready(p["id"]) for p in self._all())

    def local_ids(self) -> set[str]:
        return {p["id"] for p in self._all() if p["local"]}

    # -- change ------------------------------------------------------------------------------------------------
    def add(self, name: str, base_url: str, api_key: str = "", preset: str | None = None) -> dict[str, Any]:
        name = " ".join((name or "").split())[:40]
        if not name:
            raise ValueError("Give this provider a name")
        url = clean_base_url(base_url)
        local = is_local_url(url)
        key = (api_key or "").strip()
        if not local and not key:
            raise ValueError("This provider needs an API key")
        with self._lock:
            rows = self._read()
            if any(p["base_url"].rstrip("/") == url for p in [*rows, *([self._builtin()] if self._builtin() else [])]):
                raise ValueError("This provider address has already been added")
            slug = re.sub(r"[^a-z0-9]+", "-", (preset or name).lower()).strip("-") or "provider"
            ids = {r["id"] for r in rows} | {BUILTIN_ID}
            pid, n = slug, 2
            while pid in ids:
                pid, n = f"{slug}-{n}", n + 1
            row = {"id": pid, "name": name, "base_url": url, "api_key": key, "local": local}
            self._write([*rows, row])
        return self._public({**row, "builtin": False})

    def update(self, provider_id: str, *, name: str | None = None, base_url: str | None = None, api_key: str | None = None) -> dict[str, Any]:
        with self._lock:
            rows = self._read()
            row = next((r for r in rows if r["id"] == provider_id), None)
            if row is None:
                raise KeyError(provider_id)
            if name is not None:
                row["name"] = " ".join(name.split())[:40] or row["name"]
            if base_url is not None:
                row["base_url"] = clean_base_url(base_url)
                row["local"] = is_local_url(row["base_url"])
            if api_key is not None and api_key.strip():  # an empty field means "keep the saved key"
                row["api_key"] = api_key.strip()
            self._write(rows)
        return self._public({**row, "builtin": False})

    def delete(self, provider_id: str) -> bool:
        with self._lock:
            rows = self._read()
            kept = [r for r in rows if r["id"] != provider_id]
            if len(kept) == len(rows):
                return False
            self._write(kept)
            return True
