"""User-changeable runtime settings, kept in ui_data/settings.json and applied over the .env defaults.

Secrets (API keys) never pass through here: they stay in .env. Only the choice of source/model and a few
switches are stored.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SOURCES = {"Codex": "ChatGPT (log in in Settings)", "Custom": "OpenAI-compatible API (such as OpenRouter)"}
KEYS = ("source", "model", "model_id", "use_tool_retriever", "commercial_mode", "reasoning_effort")


def load(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: data[k] for k in KEYS if k in data}


def validate(values: dict[str, Any], *, custom_ready: bool) -> dict[str, Any]:
    """Return the cleaned subset of `values`, or raise ValueError with a readable message."""
    out: dict[str, Any] = {}
    if "source" in values:
        if values["source"] not in SOURCES:
            raise ValueError(f"Unsupported model source: {values['source']}")
        if values["source"] == "Custom" and not custom_ready:
            raise ValueError("No OpenAI-compatible address and key are set in .env (BIOMNI_CUSTOM_BASE_URL / BIOMNI_CUSTOM_API_KEY)")
        out["source"] = values["source"]
    if "model" in values:
        model = str(values["model"]).strip()
        if not model or len(model) > 120:
            raise ValueError("The model name cannot be empty or longer than 120 characters")
        out["model"] = model
    for k in ("use_tool_retriever", "commercial_mode"):
        if k in values:
            if not isinstance(values[k], bool):
                raise ValueError(f"{k} must be true or false")
            out[k] = values[k]
    return out


def check_codex_model(source: str | None, model: str | None) -> str | None:
    """Return the model to store for the Codex source, or raise: only gpt-6-luna is allowed."""
    from biomni_ui.codex_llm import resolve_model

    return resolve_model(model) if source == "Codex" else model


def save(path: Path, current: dict[str, Any], changes: dict[str, Any]) -> dict[str, Any]:
    merged = {**current, **changes}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    return merged


def apply(cfg, values: dict[str, Any]) -> None:
    """Apply stored values to the live BiomniConfig (mutated in place; the agent reads it at construction)."""
    if "source" in values:
        cfg.source = values["source"]
    if "model" in values:
        cfg.llm = values["model"]
    if "use_tool_retriever" in values:
        cfg.use_tool_retriever = values["use_tool_retriever"]
    if "commercial_mode" in values:
        cfg.commercial_mode = values["commercial_mode"]
