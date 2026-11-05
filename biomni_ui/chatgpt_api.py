"""ChatGPT membership as a plain model: sign in once, then call the ChatGPT backend directly.

`codex exec` (codex_llm.py) is a whole agent: it loads the user's Codex plugins and MCP servers and uses them instead of
the host program's tools. This module talks to the same backend as the CLI does (the Responses endpoint behind
chatgpt.com/backend-api/codex) but sends only messages, so the model has no tools of its own.

Sign-in is OpenAI's device-code flow, started from this app. The tokens are kept in `ui_data/chatgpt_auth.json`, a file
owned by this app; nothing here reads or copies the Codex CLI's or any other program's credentials.
"""

from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path
from typing import Any, Iterator

import httpx

from biomni_ui import llm_calls
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

ISSUER = "https://auth.openai.com"
CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"  # the public client id of OpenAI's Codex sign-in
TOKEN_URL = f"{ISSUER}/oauth/token"
BASE_URL = "https://chatgpt.com/backend-api/codex"
USER_AGENT = "BiomniLite/0.1"
AUTH_FILE = Path(__file__).resolve().parent.parent / "ui_data" / "chatgpt_auth.json"
REFRESH_SKEW = 300  # refresh when the access token has less than 5 minutes left


class ChatGPTAuthError(RuntimeError):
    pass


# ---- token file -------------------------------------------------------------------------------------------------

def load_tokens(path: Path = AUTH_FILE) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if data.get("access_token") else None


def save_tokens(tokens: dict[str, Any], path: Path = AUTH_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(tokens), encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    tmp.replace(path)


def is_logged_in(path: Path = AUTH_FILE) -> bool:
    return load_tokens(path) is not None


def logout(path: Path = AUTH_FILE) -> None:
    try:
        path.unlink()
    except OSError:
        pass


def _jwt_claims(token: str) -> dict[str, Any]:
    try:
        part = token.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
    except Exception:
        return {}


def account_headers(access_token: str) -> dict[str, str]:
    """Workspace headers the backend reads from the token (same ones the official client sends)."""
    auth = _jwt_claims(access_token).get("https://api.openai.com/auth", {})
    out = {}
    if isinstance(auth.get("chatgpt_account_id"), str) and auth["chatgpt_account_id"]:
        out["ChatGPT-Account-ID"] = auth["chatgpt_account_id"]
    residency = auth.get("chatgpt_data_residency") or auth.get("chatgpt_compute_residency")
    if isinstance(residency, str) and residency.strip():
        out["x-openai-internal-codex-residency"] = residency.strip()
    return out


def _expires_soon(access_token: str, skew: int = REFRESH_SKEW) -> bool:
    exp = _jwt_claims(access_token).get("exp")
    return not isinstance(exp, (int, float)) or exp - time.time() < skew


def fresh_access_token(path: Path = AUTH_FILE) -> str:
    """A valid access token, refreshing it (and rewriting the file) when it is about to expire."""
    tokens = load_tokens(path)
    if not tokens:
        raise ChatGPTAuthError("Not logged in to ChatGPT. On the Settings page, click “Log in to ChatGPT”, or run python -m biomni_ui.chatgpt_login")
    if not _expires_soon(tokens["access_token"]):
        return tokens["access_token"]
    refresh = tokens.get("refresh_token")
    if not refresh:
        raise ChatGPTAuthError("The ChatGPT login has expired. Log in again.")
    resp = httpx.post(
        TOKEN_URL,
        data={"grant_type": "refresh_token", "refresh_token": refresh, "client_id": CLIENT_ID},
        headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": USER_AGENT},
        timeout=30,
    )
    if resp.status_code != 200:
        raise ChatGPTAuthError(f"Refreshing the ChatGPT login failed (HTTP {resp.status_code}). Log in again.")
    new = resp.json()
    tokens = {**tokens, "access_token": new["access_token"], "refresh_token": new.get("refresh_token", refresh),
              "last_refresh": time.time()}
    save_tokens(tokens, path)
    return tokens["access_token"]


# ---- device-code sign-in -----------------------------------------------------------------------------------------

def request_device_code() -> dict[str, Any]:
    """Step 1: ask for a code the user types at https://auth.openai.com/codex/device."""
    resp = httpx.post(f"{ISSUER}/api/accounts/deviceauth/usercode", json={"client_id": CLIENT_ID},
                      headers={"Content-Type": "application/json", "User-Agent": USER_AGENT}, timeout=30)
    if resp.status_code == 429:
        raise ChatGPTAuthError("OpenAI is limiting login requests for now (429). Try again later.")
    if resp.status_code != 200:
        raise ChatGPTAuthError(f"Could not get a login code (HTTP {resp.status_code}).")
    data = resp.json()
    if not data.get("user_code") or not data.get("device_auth_id"):
        raise ChatGPTAuthError("The login code response was incomplete.")
    data["interval"] = max(3, int(data.get("interval") or 5))
    data["verification_url"] = f"{ISSUER}/codex/device"
    return data


def poll_device_code(device: dict[str, Any], timeout: int = 15 * 60, path: Path = AUTH_FILE) -> dict[str, Any]:
    """Steps 3-4: wait until the user finishes signing in, then exchange the result for tokens and store them."""
    deadline = time.monotonic() + timeout
    code_resp = None
    with httpx.Client(timeout=15, headers={"User-Agent": USER_AGENT}) as client:
        while time.monotonic() < deadline:
            time.sleep(device["interval"])
            try:
                r = client.post(f"{ISSUER}/api/accounts/deviceauth/token",
                                json={"device_auth_id": device["device_auth_id"], "user_code": device["user_code"]})
            except httpx.TransportError:
                continue
            if r.status_code == 200:
                code_resp = r.json()
                break
            if r.status_code not in (403, 404):  # 403/404: not finished yet
                raise ChatGPTAuthError(f"Error while waiting for login (HTTP {r.status_code}).")
        if code_resp is None:
            raise ChatGPTAuthError("Login timed out (15 minutes).")
        tr = client.post(
            TOKEN_URL,
            data={"grant_type": "authorization_code", "code": code_resp.get("authorization_code", ""),
                  "redirect_uri": f"{ISSUER}/deviceauth/callback", "client_id": CLIENT_ID,
                  "code_verifier": code_resp.get("code_verifier", "")},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if tr.status_code != 200 or not tr.json().get("access_token"):
        raise ChatGPTAuthError(f"Could not exchange for login credentials (HTTP {tr.status_code}).")
    t = tr.json()
    tokens = {"access_token": t["access_token"], "refresh_token": t.get("refresh_token", ""), "last_refresh": time.time()}
    save_tokens(tokens, path)
    return tokens


# ---- the model ---------------------------------------------------------------------------------------------------

def build_request(messages: list[BaseMessage], model: str, effort: str, search: bool = False) -> dict[str, Any]:
    """LangChain messages -> a Responses API body. System messages become `instructions`."""
    instructions, items = [], []
    for m in messages:
        text = m.content if isinstance(m.content, str) else str(m.content)
        if m.type == "system":
            instructions.append(text)
        elif m.type == "ai":
            items.append({"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}]})
        else:
            items.append({"type": "message", "role": "user", "content": [{"type": "input_text", "text": text}]})
    if not items:
        items.append({"type": "message", "role": "user", "content": [{"type": "input_text", "text": "."}]})
    body = {
        "model": model,
        "instructions": "\n\n".join(instructions) or "You are a helpful assistant.",
        "input": items,
        "tools": [],
        "tool_choice": "none",
        "parallel_tool_calls": False,
        "store": False,
        "stream": True,
        "reasoning": {"effort": effort},
    }
    if search:  # the model may search the web inside the same reply (what the official app does); sources come back with the call
        body.update(tools=[{"type": "web_search"}], tool_choice="auto", include=["web_search_call.action.sources"])
    return body


def iter_sse(lines: Iterator[str]) -> Iterator[dict[str, Any]]:
    """Server-sent events -> the JSON payload of each `data:` line."""
    for line in lines:
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            yield json.loads(payload)
        except ValueError:
            continue


def collect_text(events: Iterator[dict[str, Any]]) -> str:
    """The assistant text of a streamed response; raises on a failed one."""
    return collect(events)[0]


def collect(events: Iterator[dict[str, Any]], stops: list[str] | None = None, on_text: Any = None) -> tuple[str, dict[str, Any]]:
    """(assistant text, what the server reports about the call: effort it applied and token usage).

    With `stops`, reading ends as soon as one of them has appeared (the caller closes the connection, so the model's
    tail is neither generated nor waited for). The server then sends no usage, so `info["stopped_early"]` is set.
    """
    parts: list[str] = []
    final = ""
    info: dict[str, Any] = {}
    for ev in events:
        kind = ev.get("type", "")
        if kind in ("response.created", "response.in_progress"):  # the server states the effort it applies before any text
            seen = (ev.get("response") or {}).get("reasoning") or {}
            if seen.get("effort"):
                info = {**info, "effort": seen["effort"], "model": (ev.get("response") or {}).get("model")}
        if kind == "response.completed":
            resp = ev.get("response") or {}
            info = {**info, "usage": resp.get("usage") or {}, "effort": (resp.get("reasoning") or {}).get("effort"), "model": resp.get("model")}
        if kind == "response.output_text.delta":
            parts.append(ev.get("delta", ""))
            if on_text is not None:
                on_text("".join(parts))
            if stops and any(st in "".join(parts) for st in stops):
                info = {**info, "stopped_early": True}
                break
        elif kind == "response.output_item.done":
            item = ev.get("item") or {}
            if item.get("type") == "web_search_call":
                info.setdefault("searches", []).append(item.get("action") or {})
            if item.get("type") == "message" and not parts:
                final = "".join(c.get("text", "") for c in item.get("content", []) if c.get("type") == "output_text")
        elif kind in ("response.failed", "error"):
            err = (ev.get("response") or {}).get("error") or ev.get("error") or ev
            raise RuntimeError(f"ChatGPT returned an error: {str(err.get('message', err))[:300]}")
    return ("".join(parts) or final).strip(), info


def as_agent_reply(text: str) -> str:
    """After a web search the model just answers in plain prose; the agent needs <solution> (or <execute>), or it asks again."""
    t = text.strip()
    if not t or "<execute>" in t or "<solution>" in t:
        return text
    return f"<solution>{t}</solution>"


def search_activity(searches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The model's own web searches as step-card items: {tool, query, results[{title,url,domain}]}."""
    from urllib.parse import urlparse

    out: list[dict[str, Any]] = []
    for a in searches:
        kind = a.get("type")
        if kind == "search":
            queries = a.get("queries") or [a.get("query", "")]
            results = []
            for src in a.get("sources") or []:
                url = src.get("url") if isinstance(src, dict) else None
                if url:
                    results.append({"title": src.get("title", "") or "", "url": url, "domain": urlparse(url).netloc, "snippet": ""})
                elif isinstance(src, dict) and src.get("name"):
                    results.append({"title": f"Data service: {src['name']}", "url": "", "domain": src["name"], "snippet": ""})
            out.append({"tool": "web_search", "query": " / ".join(q for q in queries if q)[:300], "results": [r for r in results if r["url"]], "text": "" if results else "(the search service returned no sources)"})
        elif kind in ("open_page", "find_in_page"):
            url = a.get("url", "")
            out.append({"tool": "web_search", "query": f"Open web page {url}"[:300], "results": [{"title": url, "url": url, "domain": urlparse(url).netloc, "snippet": ""}] if url else []})
    return out


def _throttled(fn: Any, every: float = 0.5) -> Any:
    """Call `fn(text)` at most every `every` seconds, always with the latest text."""
    last = [0.0]

    def call(text: str) -> None:
        now = time.time()
        if now - last[0] >= every:
            last[0] = now
            fn(text)

    return call


def explain_http_error(status: int, body: str) -> str:
    low = body.lower()
    if status == 401:
        return "The ChatGPT login is no longer valid. Log in again."
    if status == 429 or "usage limit" in low:
        return "ChatGPT usage is used up or rate-limited. Try again later."
    if status == 400 and "model" in low:
        return f"ChatGPT does not accept this model name: {body[:200]}"
    return f"The ChatGPT API returned HTTP {status}: {body[:300]}"


class ChatCodexAPI(BaseChatModel):
    """gpt-6-luna through the ChatGPT backend; same constructor shape as ChatCodex so the two are interchangeable."""

    model: str | None = None
    timeout: int = 600
    stop_sequences: list[str] | None = None
    reasoning_effort: str = "high"
    auth_path: str | None = None
    native_search: bool = False

    @property
    def _llm_type(self) -> str:
        return "chatgpt-backend"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        from biomni_ui.codex_llm import resolve_effort, resolve_model, truncate_at_stop

        path = Path(self.auth_path) if self.auth_path else AUTH_FILE
        token = fresh_access_token(path)
        body = build_request(messages, resolve_model(self.model), resolve_effort(self.reasoning_effort), search=self.native_search)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "User-Agent": USER_AGENT,
            "originator": "biomni-lite",
            **account_headers(token),
        }
        started = time.time()
        stops = [*(stop or []), *(self.stop_sequences or [])]
        for attempt in range(3):  # a dropped connection before any answer arrived is worth another try
            try:
                with httpx.Client(timeout=httpx.Timeout(self.timeout, connect=30)) as client:
                    with client.stream("POST", f"{BASE_URL}/responses", json=body, headers=headers) as resp:
                        if resp.status_code != 200:
                            resp.read()
                            raise RuntimeError(explain_http_error(resp.status_code, resp.text))
                        text, info = collect(iter_sse(resp.iter_lines()), stops, _throttled(llm_calls.push_draft))
                break
            except (httpx.ConnectError, httpx.RemoteProtocolError, httpx.ConnectTimeout):
                if attempt == 2:
                    raise
                time.sleep(1.5 * (attempt + 1))
        text = truncate_at_stop(text, stops)
        if self.native_search and not text.strip():  # searched, then wrote nothing: ask once more, this time without the search tool
            retry = {**body, "tools": [], "tool_choice": "none"}
            retry.pop("include", None)
            with httpx.Client(timeout=httpx.Timeout(self.timeout, connect=30)) as client:
                with client.stream("POST", f"{BASE_URL}/responses", json=retry, headers=headers) as resp:
                    if resp.status_code == 200:
                        text2, info2 = collect(iter_sse(resp.iter_lines()), stops, _throttled(llm_calls.push_draft))
                        text, info = truncate_at_stop(text2, stops), {**info, **{k: v for k, v in info2.items() if k != "searches"}}
        if self.native_search and info.get("searches"):
            text = as_agent_reply(text)
        if info.get("searches"):
            from biomni_ui.codex_llm import push_activity

            push_activity(search_activity(info["searches"]))
        usage = info.get("usage") or {}
        if info.get("stopped_early") and not usage:  # no usage arrives when we hang up; estimate from what we read
            usage = {"output_tokens": max(1, len(text) // 3), "input_tokens": sum(len(str(m.content)) for m in messages) // 3}
        message = AIMessage(
            content=text,
            usage_metadata={
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
                "output_token_details": {"reasoning": (usage.get("output_tokens_details") or {}).get("reasoning_tokens", 0)},
            },
            # `effort` is what the server says it applied, not what we asked for
            response_metadata={"model": info.get("model") or body["model"], "effort": info.get("effort") or body["reasoning"]["effort"], "seconds": round(time.time() - started, 1)},
        )
        return ChatResult(generations=[ChatGeneration(message=message)])
