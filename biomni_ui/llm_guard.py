"""Enforce the agent's stop sequences on the client side, without touching upstream agent code.

The agent protocol is: the model writes <execute>code</execute> and stops; the harness runs the code and
replies with <observation>. Models that ignore the API `stop` parameter keep going and invent the
observation (and even a <solution>) themselves. Upstream then prefers the <solution> and finishes with an
invented answer before the code has run. This wrapper cuts the reply right after the first closing tag, which
is what a real stop sequence would have done.
"""

from __future__ import annotations

import time
from typing import Any

from biomni_ui import llm_calls

CLOSERS = ("</execute>", "</solution>")


def cut_after_first_close(text: str) -> str:
    ends = [text.find(t) + len(t) for t in CLOSERS if t in text]
    return text[: min(ends)] if ends else text


class StopGuardLLM:
    """Delegates everything to `inner`; only `invoke` post-processes the reply."""

    def __init__(self, inner: Any, *, model: str | None = None, effort: str | None = None):
        object.__setattr__(self, "_inner", inner)
        # what was asked for; the reply's own metadata (what the server applied) wins when it is there
        object.__setattr__(self, "_model", model)
        object.__setattr__(self, "_effort", effort)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(self._inner, name, value)

    def invoke(self, *args: Any, **kwargs: Any):
        started = time.time()
        reply = self._inner.invoke(*args, **kwargs)
        llm_calls.record(llm_calls.from_reply(reply, model=self._model, effort=self._effort, seconds=time.time() - started))
        content = getattr(reply, "content", None)
        if isinstance(content, str):
            cut = cut_after_first_close(content)
            if cut != content:
                reply = reply.model_copy(update={"content": cut}) if hasattr(reply, "model_copy") else reply
        return reply


def guard(agent: Any) -> None:
    """Wrap `agent.llm` once. The agent reads `self.llm` at call time, so no upstream change is needed."""
    if not isinstance(agent.llm, StopGuardLLM):
        agent.llm = StopGuardLLM(agent.llm)
