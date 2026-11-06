"""LangChain chat model that talks to ChatGPT through the locally logged-in Codex CLI.

A ChatGPT membership is not an OpenAI API key, so Biomni-Desk cannot use it through the
"OpenAI" source. This wrapper shells out to `codex exec` (the official CLI, using its own
login) once per call. Nothing here reads or copies the CLI's credentials.

Limits compared with a native API: one process per call (slower), no token streaming,
and `stop` sequences are emulated by truncating the reply.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from biomni_ui import effort as effort_levels
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

_ROLE_LABEL = {"system": "SYSTEM", "human": "USER", "ai": "ASSISTANT"}

# Codex is itself an agent: left alone it searches the web or calls its own tools and replies with a finished
# answer, which bypasses the host program's tools and leaves nothing to trace. This text turns it into a plain
# text model that only follows the host's protocol.
_PREAMBLE = (
    "You are acting as a PURE TEXT-COMPLETION MODEL inside another program. In this session you have NO tools: "
    "do not search the web, do not run any shell command, do not call any MCP tool, plugin, connector or browser, "
    "and do not read or write files. The only way to get information is the protocol described in the SYSTEM "
    "section below (for example: you write <execute>code</execute> and STOP; the host program runs it and shows "
    "you the result in a later turn). Never write <solution> before you have seen an <observation> from the host. "
    "Output exactly one assistant message that follows the SYSTEM instructions, and nothing else. "
    "If you need data, write code for the host to run instead of answering from memory or from tools you think you have."
)


def render_prompt(messages: list[BaseMessage]) -> str:
    parts = [_PREAMBLE, ""]
    for m in messages:
        label = _ROLE_LABEL.get(m.type, m.type.upper())
        content = m.content if isinstance(m.content, str) else str(m.content)
        parts.append(f"[{label}]\n{content}\n")
    parts.append("[ASSISTANT]")
    return "\n".join(parts)


def truncate_at_stop(text: str, stop: list[str] | None) -> str:
    """Cut `text` before the earliest stop sequence, as a real API would."""
    if not stop:
        return text
    cut = len(text)
    for s in stop:
        i = text.find(s)
        if i != -1:
            cut = min(cut, i)
    return text[:cut]


# CLI features that give the model tools of its own (shell, browser, computer use, plugins, sub-agents...).
CLI_TOOL_FEATURES = (
    "apps", "plugins", "browser_use", "computer_use", "in_app_browser", "shell_tool", "unified_exec",
    "multi_agent", "memories", "tool_suggest", "skill_search",
)

# Item types the CLI emits when it acts on its own instead of just answering.
CLI_TOOL_ITEMS = {"command_execution", "mcp_tool_call", "web_search", "file_change", "collab_tool_call"}

def _json_lines(stdout: str) -> list[dict]:
    out = []
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out


def cli_tool_uses(stdout: str) -> list[str]:
    """Names of the CLI's own tools used in a `codex exec --json` run (empty means it only produced text)."""
    return [e["item"]["type"] for e in _json_lines(stdout)
            if e.get("type") == "item.completed" and (e.get("item") or {}).get("type") in CLI_TOOL_ITEMS]


_ACTIVITY: list[dict] = []
_ACTIVITY_LOCK = threading.Lock()
MAX_TEXT = 4000


def _flatten(value: Any) -> str:
    """Best-effort text of an MCP / command result, whatever shape the CLI used."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(_flatten(v) for v in value)
    if isinstance(value, dict):
        if "text" in value and isinstance(value["text"], str):
            return value["text"]
        return "\n".join(f"{k}: {_flatten(v)}" for k, v in value.items() if k not in ("type", "id"))
    return str(value)


def normalize_item(item: dict) -> dict | None:
    """A CLI-side tool item -> {tool, query?, results?, text?}; None for items that are not tool use."""
    kind = item.get("type")
    if kind not in CLI_TOOL_ITEMS:
        return None
    if kind == "web_search":
        queries = (item.get("action") or {}).get("queries") or [item.get("query", "")]
        results = [
            {"title": r.get("title", ""), "url": r.get("url", ""), "domain": r.get("domain", ""), "snippet": (r.get("snippet") or "")[:400]}
            for r in item.get("results") or []
            if isinstance(r, dict) and r.get("url")
        ]
        return {"tool": "web_search", "query": " / ".join(q for q in queries if q)[:300], "results": results}
    if kind == "mcp_tool_call":
        name = ".".join(x for x in (item.get("server"), item.get("tool")) if x) or "mcp"
        return {"tool": name, "query": _flatten(item.get("arguments"))[:300], "text": _flatten(item.get("result"))[:MAX_TEXT]}
    if kind == "command_execution":
        return {"tool": "shell", "query": str(item.get("command", ""))[:300], "text": _flatten(item.get("aggregated_output"))[:MAX_TEXT]}
    return {"tool": kind, "query": "", "text": _flatten(item)[:MAX_TEXT]}


def record_activity(stdout: str) -> None:
    items = [normalize_item(e["item"]) for e in _json_lines(stdout)
             if e.get("type") == "item.completed" and isinstance(e.get("item"), dict)]
    items = [i for i in items if i]
    if items:
        with _ACTIVITY_LOCK:
            _ACTIVITY.extend(items)


def push_activity(items: list[dict]) -> None:
    if items:
        with _ACTIVITY_LOCK:
            _ACTIVITY.extend(items)


def drain_activity() -> list[dict]:
    """Everything the CLI did with its own tools since the last call (and clear it)."""
    with _ACTIVITY_LOCK:
        out = list(_ACTIVITY)
        _ACTIVITY.clear()
    return out


def _log_violation(used: list[str]) -> None:
    try:
        log = Path(__file__).resolve().parent.parent / "ui_data" / "codex_tool_use.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} used its own CLI tools: {sorted(set(used))}\n")
    except OSError:
        pass


def explain_failure(returncode: int, stderr: str, stdout: str = "") -> str:
    """A readable reason for a failed `codex exec`.

    The CLI echoes the whole prompt, so the raw tail is useless. Its real errors are the `ERROR:` lines.
    """
    text = f"{stderr}\n{stdout}"
    for e in _json_lines(stdout):
        msg = e.get("message") or (e.get("error") or {}).get("message") if e.get("type") in ("error", "turn.failed") else None
        if msg:
            text += f"\nERROR: {msg}"
    errors = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("ERROR:") and line not in errors:
            errors.append(line)
    joined = " ".join(errors)
    if "usage limit" in joined.lower():
        m = re.search(r"try again at ([^.]+?\d{4}[^.]*?(?:AM|PM))", joined)
        when = f", expected to reset {m.group(1)}" if m else ""
        return (
            f"ChatGPT usage is used up{when}."
            " You can switch the model source to an OpenAI-compatible API (such as OpenRouter) on the Settings page, or upgrade your plan."
        )
    if "login" in joined.lower() or "unauthorized" in joined.lower() or "401" in joined:
        return "Codex is not logged in, or the login has expired. Run `codex login` in a terminal, then try again."
    if errors:
        return f"codex exec failed (exit code {returncode}): {joined[:300]}"
    return f"codex exec returned no output (exit code {returncode}). Run `codex exec \"hi\"` to see why."


# Policy: of the GPT models only gpt-6-luna may be used through ChatGPT. Never fall back to the CLI default.
GPT_MODEL = "gpt-6-luna"


def resolve_model(model: str | None) -> str:
    if model in (None, "", "default", GPT_MODEL):
        return GPT_MODEL
    raise ValueError(f"ChatGPT only allows {GPT_MODEL}, but received {model}")


def resolve_effort(effort: str | None) -> str:
    effort = (effort or "high").strip().lower()
    if effort not in ("low", "medium", "high", "xhigh"):
        raise ValueError(f"Reasoning effort must be medium, high or xhigh, but received {effort}")
    return effort_levels.floor(effort)  # a stored "low" is raised to the starting tier


class ChatCodex(BaseChatModel):
    model: str | None = None
    timeout: int = 600
    codex_bin: str | None = None
    stop_sequences: list[str] | None = None
    reasoning_effort: str = "high"  # low | medium | high | xhigh
    native_search: bool = False  # let the model search the web inside its own reply (ChatGPT backend only)

    @property
    def _llm_type(self) -> str:
        return "codex-cli"

    def _run_once(self, exe: str, prompt: str) -> tuple[str, list[str]]:
        """One `codex exec`. Returns (reply text, names of CLI-side tools it used)."""
        with tempfile.TemporaryDirectory(prefix="biomni-codex-") as work:
            out_file = Path(work) / "last.txt"
            cmd = [
                exe, "exec",
                "--skip-git-repo-check", "--ephemeral",
                "-s", "read-only",
                "-C", work,
                "--json",
                "-o", str(out_file),
            ]
            cmd += ["-m", resolve_model(self.model), "-c", f'model_reasoning_effort="{resolve_effort(self.reasoning_effort)}"']
            # Switch off the CLI's own tools so the model has to use Biomni's (measured: with these flags the run
            # emits only agent_message items; without them it web-searches and skips the host's database tools).
            cmd += ["-c", 'web_search="disabled"']
            for feature in CLI_TOOL_FEATURES:
                cmd += ["--disable", feature]
            cmd.append("-")
            proc = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self.timeout,
                env={**os.environ},
            )
            if not out_file.exists():
                raise RuntimeError(explain_failure(proc.returncode, proc.stderr or "", proc.stdout or ""))
            record_activity(proc.stdout or "")
            return out_file.read_text(encoding="utf-8").strip(), cli_tool_uses(proc.stdout or "")

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        from biomni_ui import chatgpt_api

        if chatgpt_api.is_logged_in():
            # Preferred: the ChatGPT backend as a plain model (no CLI, so no plugins / MCP tools of its own).
            return chatgpt_api.ChatCodexAPI(
                model=self.model, timeout=self.timeout, reasoning_effort=self.reasoning_effort,
                stop_sequences=self.stop_sequences, native_search=self.native_search,
            )._generate(messages, stop, run_manager, **kwargs)

        exe = self.codex_bin or shutil.which("codex")
        if not exe:
            raise RuntimeError("The codex command was not found. Install and log in to the Codex CLI first.")

        text, used = self._run_once(exe, render_prompt(messages))
        if used:
            # gpt-6-luna often searches the web itself instead of using the host's tools, even when told not to.
            # Retrying does not change that (measured) and doubles the wait, so only record it; the answer's
            # sources are checked against PubMed / Crossref / the page itself in the UI instead.
            _log_violation(used)

        text = truncate_at_stop(text, [*(stop or []), *(self.stop_sequences or [])])
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])
