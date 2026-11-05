"""The general loop on any model: one streamed call to an OpenAI-compatible chat-completions endpoint, with function calling.

The loop (native_agent) speaks in "items" (the shape the ChatGPT backend uses: messages, function calls, function call outputs).
This module turns them into chat messages, makes one call, and turns the reply back into items, so the same loop, the same tools
and the same prompt run on OpenRouter models, a local server, or any provider that offers tool calls. A model that cannot call
tools raises ToolsUnsupported and the caller falls back to the older agent.
"""

from __future__ import annotations

import json
import time
from typing import Any, Callable

import httpx


class ToolsUnsupported(RuntimeError):
    """The endpoint or model refused the request because it cannot use tools."""


def chat_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Function tools in the chat-completions shape. A provider-side tool such as the ChatGPT web search has no equivalent here and is dropped."""
    out = []
    for t in tools:
        if t.get("type") == "function" and t.get("name"):
            out.append({"type": "function", "function": {"name": t["name"], "description": t.get("description", ""), "parameters": t.get("parameters") or {"type": "object", "properties": {}}}})
    return out


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    return "".join(str(p.get("text", "")) for p in content or [] if isinstance(p, dict))


def to_messages(instructions: str, items: list[dict[str, Any]], echo_reasoning: bool = False) -> list[dict[str, Any]]:
    """Items -> chat messages. Reasoning items and provider-side search calls (kept in a conversation that used the ChatGPT backend) are dropped;
    function calls that follow an assistant message join it, as chat endpoints expect."""
    messages: list[dict[str, Any]] = [{"role": "system", "content": instructions}]
    assistant: dict[str, Any] | None = None  # the assistant message being built (text and/or tool calls)

    def flush() -> None:
        nonlocal assistant
        if assistant is not None:
            if not assistant.get("tool_calls"):
                assistant.pop("tool_calls", None)
            messages.append(assistant)
            assistant = None

    for it in items:
        kind = it.get("type")
        if kind == "chat_reasoning":  # the model's reasoning_content, kept so a provider that demands it back in thinking mode gets it
            if assistant is None:
                assistant = {"role": "assistant", "content": "", "tool_calls": []}
            assistant["reasoning_content"] = str(it.get("text") or "")
        elif kind == "message":
            role = it.get("role", "user")
            if role == "assistant":
                if assistant is None:
                    assistant = {"role": "assistant", "content": "", "tool_calls": []}
                assistant["content"] = (assistant["content"] + "\n" + _text(it.get("content"))).strip()
            else:
                flush()
                messages.append({"role": "user" if role != "system" else "system", "content": _text(it.get("content"))})
        elif kind == "function_call":
            if assistant is None:
                assistant = {"role": "assistant", "content": "", "tool_calls": []}
            assistant["tool_calls"].append({"id": it.get("call_id") or f"call_{len(messages)}", "type": "function",
                                            "function": {"name": it.get("name", ""), "arguments": it.get("arguments") or "{}"}})
        elif kind == "function_call_output":
            flush()
            messages.append({"role": "tool", "tool_call_id": it.get("call_id"), "content": str(it.get("output", ""))})
    flush()
    messages = _repair(messages)
    if echo_reasoning:  # in thinking mode every earlier assistant turn carries reasoning_content (empty when we never saw it)
        for m in messages:
            if m.get("role") == "assistant":
                m.setdefault("reasoning_content", "")
    return messages


def _repair(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Chat endpoints refuse a tool message with no tool call before it and a tool call with no tool message after it (a stopped task or a trimmed
    history leaves such halves behind). Drop the unanswered calls and the orphan outputs."""
    answered = {m.get("tool_call_id") for m in messages if m.get("role") == "tool"}
    out: list[dict[str, Any]] = []
    open_ids: set[str] = set()
    for m in messages:
        if m.get("role") == "assistant":
            calls = [c for c in m.get("tool_calls") or [] if c.get("id") in answered]
            m = {**m}
            if calls:
                m["tool_calls"] = calls
            else:
                m.pop("tool_calls", None)
            open_ids = {c["id"] for c in calls}
            if not calls and not str(m.get("content") or "").strip() and not m.get("reasoning_content"):
                continue
        elif m.get("role") == "tool":
            if m.get("tool_call_id") not in open_ids:
                continue
        else:
            open_ids = set()
        out.append(m)
    return out


_NO_TOOLS = ("support tool", "supports tool", "tool use", "tool_use", "tools are not", "tool calling", "function calling", "function call is not", "tool_choice")


def _explain(status: int, text: str) -> str:
    try:
        err = json.loads(text).get("error", {})
        msg = err.get("message") if isinstance(err, dict) else str(err)
    except ValueError:
        msg = text[:300]
    return f"{status}: {str(msg or text)[:300]}"


def call_chat(base_url: str, api_key: str, model: str, instructions: str, items: list[dict[str, Any]], tools: list[dict[str, Any]],
              on_text: Callable[[str], None] | None = None, extra: dict[str, Any] | None = None, timeout: int = 600,
              client_factory: Callable[[], httpx.Client] | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """One streamed call. Returns (output items, {"seconds", "usage"}) like native_agent.call_model."""
    echo = ((extra or {}).get("thinking") or {}).get("type") == "enabled"
    body: dict[str, Any] = {"model": model, "messages": to_messages(instructions, items, echo), "stream": True, "stream_options": {"include_usage": True}}
    fn_tools = chat_tools(tools)
    if fn_tools:
        body.update(tools=fn_tools, tool_choice="auto")
    body.update(extra or {})
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "Accept": "text/event-stream"}
    url = base_url.rstrip("/") + "/chat/completions"
    t0 = time.time()
    last: Exception | None = None
    for attempt in range(3):
        text_parts: list[str] = []
        thinking: list[str] = []
        calls: dict[int, dict[str, str]] = {}
        usage: dict[str, Any] = {}
        try:
            with (client_factory() if client_factory else httpx.Client(timeout=httpx.Timeout(timeout, connect=30))) as client:
                with client.stream("POST", url, json=body, headers=headers) as resp:
                    if resp.status_code != 200:
                        resp.read()
                        detail = _explain(resp.status_code, resp.text)
                        if resp.status_code in (400, 404, 422) and any(w in detail.lower() for w in _NO_TOOLS):
                            raise ToolsUnsupported(detail)
                        if resp.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                            raise ConnectionError(detail)
                        raise RuntimeError(detail)
                    for line in resp.iter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                        except ValueError:
                            continue
                        if chunk.get("error"):
                            raise RuntimeError(str(chunk["error"])[:300])
                        if chunk.get("usage"):
                            usage = chunk["usage"]
                        for choice in chunk.get("choices") or []:
                            delta = choice.get("delta") or {}
                            if delta.get("reasoning_content"):
                                thinking.append(delta["reasoning_content"])
                            if delta.get("content"):
                                text_parts.append(delta["content"])
                                if on_text:
                                    on_text("".join(text_parts))
                            for tc in delta.get("tool_calls") or []:
                                slot = calls.setdefault(int(tc.get("index") or 0), {"id": "", "name": "", "arguments": ""})
                                if tc.get("id"):
                                    slot["id"] = tc["id"]
                                fn = tc.get("function") or {}
                                if fn.get("name"):
                                    slot["name"] += fn["name"]
                                if fn.get("arguments"):
                                    slot["arguments"] += fn["arguments"]
            out: list[dict[str, Any]] = []
            if "".join(thinking).strip():
                out.append({"type": "chat_reasoning", "text": "".join(thinking)})
            if "".join(text_parts).strip():
                out.append({"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "".join(text_parts)}]})
            for i in sorted(calls):
                c = calls[i]
                if c["name"]:
                    out.append({"type": "function_call", "name": c["name"], "call_id": c["id"] or f"call_{i}_{int(t0)}", "arguments": c["arguments"] or "{}"})
            detail = usage.get("completion_tokens_details") or {}
            return out, {"seconds": round(time.time() - t0, 1), "usage": {"input_tokens": usage.get("prompt_tokens"), "output_tokens": usage.get("completion_tokens"),
                                                                           "output_tokens_details": {"reasoning_tokens": detail.get("reasoning_tokens")}}}
        except (httpx.TransportError, ConnectionError) as e:  # a dropped connection or a busy endpoint: try again
            last = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Connecting to the model API failed: {type(last).__name__}: {str(last)[:200]}")
