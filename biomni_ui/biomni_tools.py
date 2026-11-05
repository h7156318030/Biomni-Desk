"""Biomni's specialist tools for the general loop: find them by keyword, run them by name.

The loop's model has a shell and a web search. Biomni also ships 225 stock tools (database queries, genomics, pharmacology,
immunology ...) and we added fast ones (author papers, trial registry, database lookups, charts, reports). Putting 250 schemas
in front of the model costs a round trip and drowns the prompt, so the model asks for them: `find_tools` ranks the catalog by
the words of a query and prints name, parameters and a one-line description; `run_tool` calls one by name with a JSON
object of arguments. They run inside this process, where the tools that need a model (the `query_*` family) are bound to ours.
"""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import pkgutil
import re
import threading
from pathlib import Path
from typing import Any

HEALTH_FILE = Path(__file__).resolve().parent.parent / "ui_data" / "tool_health.json"
_BAD = ("restricted", "missing-deps", "not-found")  # tools that cannot run on this machine are not offered
_CACHE: list[dict[str, Any]] = []
_LOCK = threading.Lock()
OUTPUT_LIMIT = 6000


def _health() -> dict[str, str]:
    try:
        from biomni_ui.tool_health import LEGACY_STATUS  # cache files written before the status tokens were English

        rows = json.loads(HEALTH_FILE.read_text(encoding="utf-8")).get("rows", [])
        return {r["name"]: LEGACY_STATUS.get(r.get("status", ""), r.get("status", "")) for r in rows}
    except Exception:
        return {}


def catalog() -> list[dict[str, Any]]:
    """Every tool as {name, import (module path), description, required [(name, type)], optional [(name, type)], status}."""
    with _LOCK:
        if _CACHE:
            return _CACHE
        health = _health()
        items: list[dict[str, Any]] = []
        try:
            import biomni.tool.tool_description as td

            for m in pkgutil.iter_modules(td.__path__):
                try:
                    mod = importlib.import_module(f"biomni.tool.tool_description.{m.name}")
                except Exception:
                    continue
                for d in getattr(mod, "description", []) or []:
                    items.append(_entry(d, f"biomni.tool.{m.name}", health.get(d.get("name", ""), "available")))
        except Exception:
            pass
        try:
            from biomni_ui import fast_tools

            for d in fast_tools.SCHEMAS:
                items.append(_entry({"module": fast_tools.MODULE, **d}, d.get("module") or fast_tools.MODULE, "available"))
        except Exception:
            pass
        _CACHE.extend(items)
        return _CACHE


def _entry(d: dict[str, Any], module: str, status: str) -> dict[str, Any]:
    return {
        "name": d.get("name", ""), "import": module, "description": " ".join(str(d.get("description", "")).split()),
        "required": [(p.get("name"), p.get("type", "")) for p in d.get("required_parameters", [])],
        "optional": [(p.get("name"), p.get("type", ""), p.get("default")) for p in d.get("optional_parameters", [])], "status": status,
    }


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) >= 2]


def find_tools(query: str, limit: int = 8) -> str:
    """The best matches for a keyword query (English words work best), with how to call each."""
    words = _words(query)
    tools = catalog()
    usable = [t for t in tools if not any(b in t["status"] for b in _BAD)]
    if not usable:
        return "No specialist tool catalogue is available."
    from biomni_ui import usage

    scored = []
    for t in usable:
        name_words = set(_words(t["name"].replace("_", " ")))
        desc = t["description"].lower()
        score = sum(3 for w in words if w in name_words) + sum(1 for w in words if w in desc)
        if score and "PREFERRED" in t["description"]:
            score += 2
        if score:  # a function used before ranks above an equal match
            score += usage.store().bonus("func", t["name"])
            scored.append((score, t))
    scored.sort(key=lambda x: -x[0])
    if not scored:
        hint = "" if words else " (the query has no English keywords; use English keywords such as 'clinical trials', 'protein', 'variant', 'pathway')"
        preferred = [t for t in usable if "PREFERRED" in t["description"]][:limit]
        if not preferred:
            return f"No matching specialist tool.{hint}"
        picked = preferred
        head = f"No tool matched the keywords{hint}; these common quick tools are listed instead:\n"
    else:
        picked = [t for _, t in scored[:limit]]
        head = f"{len(scored)} tools matched; the first {len(picked)} are listed (call with run_tool(name, arguments); arguments is a JSON object):\n"
    lines = [head]
    for t in picked:
        req = ", ".join(f"{n}: {ty}" for n, ty in t["required"]) or "none"
        opt = ", ".join(f"{n}: {ty}" + (f" = {d!r}" if d is not None else "") for n, ty, d in t["optional"]) or "none"
        lines.append(f"- {t['name']}  ({t['import']})\n  {t['description'][:260]}\n  Required parameters: {req}\n  Optional parameters: {opt}")
    lines.append(f"\n({len(usable)} usable tools in all; the {len(tools) - len(usable)} that cannot run on this machine are not listed)")
    return "\n".join(lines)


def run_tool(name: str, arguments: dict[str, Any] | None = None, timeout: int = 120) -> str:
    """Call one tool by name with keyword arguments; returns what it printed and returned, or why it failed."""
    from biomni_ui import connectors

    if not connectors.enabled(name):
        return connectors.off_message(name)
    entry = next((t for t in catalog() if t["name"] == name), None)
    if entry is None:
        return f"No tool named {name}. Look it up with find_tools first."
    if any(b in entry["status"] for b in _BAD):
        return f"Tool {name} cannot run on this computer ({entry['status']})."
    try:
        fn = getattr(importlib.import_module(entry["import"]), name)
    except Exception as e:
        return f"Could not load tool {name}: {type(e).__name__}: {str(e)[:200]}"
    args = arguments if isinstance(arguments, dict) else {}
    box: dict[str, Any] = {}
    buf = io.StringIO()

    def work() -> None:
        try:
            with contextlib.redirect_stdout(buf):
                box["value"] = fn(**args)
        except Exception as e:  # reported to the model, which may fix the arguments and retry
            box["error"] = e

    th = threading.Thread(target=work, daemon=True)
    th.start()
    th.join(timeout)
    if th.is_alive():
        return f"Tool {name} did not return within {timeout} seconds, so the wait was abandoned. Try different parameters or another tool."
    if "error" in box:
        e = box["error"]
        req = ", ".join(n for n, _ in entry["required"]) or "none"
        return f"Tool {name} failed: {type(e).__name__}: {str(e)[:300]}\nRequired parameters of this tool: {req}"
    printed = buf.getvalue().strip()
    value = box.get("value")
    text = "\n".join(x for x in (printed, "" if value is None else (value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str))) if x).strip()
    if len(text) > OUTPUT_LIMIT:
        text = text[: OUTPUT_LIMIT - 1500] + f"\n... ({len(text) - OUTPUT_LIMIT} characters omitted in the middle) ...\n" + text[-1500:]
    return text or "(the tool gave no output)"
