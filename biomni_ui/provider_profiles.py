"""What a provider's own API accepts for the model's thinking level.

OpenRouter publishes a list per model, so the page can offer exactly what each model supports. Other providers do not, but some
document their controls; for those the page offers the documented levels and the request carries the documented parameters.

DeepSeek (api.deepseek.com, docs: Thinking Mode): thinking is on by default; `reasoning_effort` takes low / high / max (default high,
"medium" is read as high); `thinking: {"type": "enabled" | "disabled"}` switches it. In thinking mode with tools every earlier
assistant turn must be sent back with its `reasoning_content`, or the API answers 400 (chat_api keeps and echoes it).
"""

from __future__ import annotations

from typing import Any

PROFILES: list[dict[str, Any]] = [
    {"host": "api.deepseek.com", "name": "DeepSeek", "efforts": ["high", "max"], "default": "high", "echo_reasoning": True},
]


def for_base_url(base_url: str | None) -> dict[str, Any] | None:
    url = (base_url or "").lower()
    return next((p for p in PROFILES if p["host"] in url), None)


def request_body(base_url: str | None, effort: str) -> dict[str, Any]:
    """The extra request fields that set `effort` for this provider ({} when the provider has no profile)."""
    prof = for_base_url(base_url)
    if not prof or effort not in prof["efforts"]:
        return {}
    return {"thinking": {"type": "enabled"}, "reasoning_effort": effort}
