"""The list of models the workbench can switch between.

Built-in entries are fixed. Users add their own OpenAI-compatible models (same endpoint and key as in .env, for
example more OpenRouter models); those are stored in ui_data/models.json. Policy: the only GPT model allowed
through ChatGPT is gpt-6-luna, so ChatGPT entries cannot be added by hand.
"""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Any

EFFORTS = ("medium", "high", "xhigh")  # the levels a user can pick: nothing below the starting tier
DEFAULT_EFFORT = "high"

BUILTIN: list[dict[str, Any]] = [
    {"id": "chatgpt-luna", "label": "ChatGPT · gpt-6-luna", "source": "Codex", "model": "gpt-6-luna",
     "note": "Included with a ChatGPT subscription, no extra charge. Log in once in Settings; requests go straight to the model. Reasoning effort can be adjusted.", "builtin": True},
    {"id": "or-nemotron-ultra", "label": "Nemotron Ultra (free)", "source": "Custom",
     "model": "nvidia/nemotron-3-ultra-550b-a55b:free", "note": "OpenRouter free model: fast, average quality", "builtin": True},
    {"id": "or-deepseek-v32", "label": "DeepSeek V3.2", "source": "Custom", "model": "deepseek/deepseek-v3.2",
     "note": "OpenRouter paid model: needs account credit", "builtin": True},
    {"id": "or-kimi-k25", "label": "Kimi K2.5", "source": "Custom", "model": "moonshotai/kimi-k2.5",
     "note": "OpenRouter paid model: needs account credit", "builtin": True},
    {"id": "or-qwen3-235b", "label": "Qwen3 235B", "source": "Custom", "model": "qwen/qwen3-235b-a22b-2507",
     "note": "OpenRouter paid model: needs account credit", "builtin": True},
    {"id": "or-nemotron-super-vl", "label": "Nemotron Super VL (free)", "source": "Custom",
     "model": "nvidia/nemotron-3.5-super-vl:free", "note": "OpenRouter free model, not individually verified", "builtin": True},
]

def cost_of(entry: dict[str, Any], local: bool = False) -> str:
    """"member" (ChatGPT membership), "local" (runs on this computer), "free" (OpenRouter :free) or "paid"
    (billed by the provider; any provider whose price we cannot see counts as paid)."""
    if entry.get("source") == "Codex":
        return "member"
    if local:
        return "local"
    return "free" if str(entry.get("model", "")).endswith(":free") else "paid"


MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/+@-]{1,119}$")


class ModelStore:
    def __init__(self, path: Path, local_providers=lambda: set()):
        self.path = path
        self._lock = threading.Lock()
        self._local_providers = local_providers  # ids of providers that run on this computer (free to use)

    def _custom(self) -> list[dict[str, Any]]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return [m for m in data.get("models", []) if isinstance(m, dict) and m.get("id") and m.get("model")]
        except (OSError, ValueError):
            return []

    def _hidden(self) -> list[str]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return [x for x in data.get("hidden", []) if isinstance(x, str)]
        except (OSError, ValueError):
            return []

    def _write(self, models: list[dict[str, Any]], hidden: list[str] | None = None) -> None:
        self._save_extra(models=models, **({} if hidden is None else {"hidden": hidden}))

    def _read(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save_extra(self, **changes: Any) -> None:
        """Rewrite the file keeping everything else in it (custom models, hidden, removed, efforts)."""
        data = {"models": self._custom(), "hidden": self._hidden(), "removed": self._read().get("removed", []), "efforts": self._read().get("efforts", {})}
        data.update(changes)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def removed(self) -> list[str]:
        return [x for x in self._read().get("removed", []) if isinstance(x, str)]

    def efforts(self) -> dict[str, str]:
        return {k: v for k, v in (self._read().get("efforts") or {}).items() if isinstance(k, str) and isinstance(v, str)}

    def set_effort(self, model_id: str, effort: str) -> None:
        with self._lock:
            self._save_extra(efforts={**self.efforts(), model_id: effort})

    def delete_provider_models(self, provider_id: str) -> int:
        """Remove every model that belongs to a provider that is being deleted; returns how many."""
        with self._lock:
            custom = self._custom()
            kept = [m for m in custom if (m.get("provider") or "openrouter") != provider_id]
            self._save_extra(models=kept)
            return len(custom) - len(kept)

    def restore_defaults(self) -> int:
        """Bring back the built-in models that were deleted; returns how many came back."""
        with self._lock:
            n = len(self.removed())
            self._save_extra(removed=[])
            return n

    def set_hidden(self, model_id: str, hidden: bool) -> bool:
        """Hide a model from the quick picker (it stays in settings). The ChatGPT entry cannot be hidden."""
        entry = next((m for m in self.list() if m["id"] == model_id), None)
        if entry is None or entry["source"] == "Codex":
            return False
        with self._lock:
            cur = [h for h in self._hidden() if h != model_id]
            self._save_extra(hidden=[*cur, model_id] if hidden else cur)
        return True

    def list(self) -> list[dict[str, Any]]:
        rows = [*({**m, "provider": "openrouter"} for m in BUILTIN), *({**m, "source": "Custom", "builtin": False, "provider": m.get("provider") or "openrouter"} for m in self._custom())]
        hidden, removed, local = set(self._hidden()), set(self.removed()), set(self._local_providers())
        return [
            {**m, "cost": cost_of(m, m.get("provider") in local), "hidden": m["id"] in hidden}
            for m in rows
            if m["id"] not in removed
        ]

    def get(self, model_id: str) -> dict[str, Any] | None:
        return next((m for m in self.list() if m["id"] == model_id), None)

    def find(self, source: str | None, model: str | None) -> dict[str, Any] | None:
        return next((m for m in self.list() if m["source"] == source and m["model"] == model), None)

    def add(self, model: str, label: str = "", note: str = "", provider: str = "openrouter") -> dict[str, Any]:
        model = model.strip()
        if not MODEL_RE.match(model):
            raise ValueError("Model name format is wrong. Use something like vendor/model-name (letters, digits and . _ : / + - only)")
        # OpenAI GPT models (openai/*, gpt-4, vendor/gpt-5 ...) are not allowed through other endpoints either.
        # (A local server's own model names, like "llama3.2:3b", are fine.)
        if re.search(r"^openai/|(^|/)gpt-?\d", model, re.IGNORECASE):
            raise ValueError("The GPT family is allowed only as gpt-6-luna through the ChatGPT entry; it cannot be added as a custom model")
        with self._lock:
            if any(m["model"] == model and m["source"] == "Custom" and m["provider"] == provider for m in self.list()):
                raise ValueError("This model is already in the list")
            custom = self._custom()
            n = 1 + max([int(m["id"][2:]) for m in custom if re.fullmatch(r"u-\d+", m["id"])] or [0])
            entry = {"id": f"u-{n}", "label": (label.strip() or model)[:60], "model": model, "note": note.strip()[:120], "provider": provider}
            self._write([*custom, entry])
        return {**entry, "source": "Custom", "builtin": False}

    def delete(self, model_id: str) -> bool:
        """Remove a model from the list. Built-in ones are only hidden away (see restore_defaults); ChatGPT stays."""
        with self._lock:
            entry = next((m for m in self.list() if m["id"] == model_id), None)
            if entry is None or entry["source"] == "Codex":
                return False
            hidden = [h for h in self._hidden() if h != model_id]
            efforts = {k: v for k, v in self.efforts().items() if k != model_id}
            if entry["builtin"]:
                self._save_extra(removed=[*self.removed(), model_id], hidden=hidden, efforts=efforts)
            else:
                self._save_extra(models=[m for m in self._custom() if m["id"] != model_id], hidden=hidden, efforts=efforts)
            return True
