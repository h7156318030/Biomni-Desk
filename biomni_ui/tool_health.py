"""Which of the stock Biomni tools can actually run on this machine, and why not when they cannot.

Static analysis only (no tool is executed): for every function behind a tool description it reads the source, finds the
packages it imports, checks they are installed, and notices whether it needs an LLM call, an API key or a command-line
program. The result is cached in ui_data/tool_health.json and shown on the Resources page, so "225 tools" is not a number
that quietly hides how many of them would fail.
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
import inspect
import json
import re
import shutil
import time
from pathlib import Path
from typing import Any

# Status tokens. The web interface translates them for display.
AVAILABLE = "available"
CONDITIONAL = "conditional"  # runs, but needs an API key, an LLM call or a one-off setup
RESTRICTED = "restricted"  # needs a local file or a command-line program that this machine does not have
MISSING = "missing-deps"  # a package it imports is not installed
NOT_FOUND = "not-found"
UNIMPORTABLE = "unimportable"
UNKNOWN = "unknown"

# Cached results written before the tokens were English are read through this table, then rescanned.
LEGACY_STATUS = {
    "可用": AVAILABLE,
    "有条件可用": CONDITIONAL,
    "受限": RESTRICTED,
    "缺依赖": MISSING,
    "未找到函数": NOT_FOUND,
    "无法导入": UNIMPORTABLE,
    "未知": UNKNOWN,
}

# import name differs from the pip name for some packages
_ALIASES = {"sklearn": "sklearn", "Bio": "Bio", "PIL": "PIL", "cv2": "cv2", "yaml": "yaml", "bs4": "bs4"}
_STDLIB = set(__import__("sys").stdlib_module_names)
_CLI = ("subprocess", "os.system")
_KEY_RE = re.compile(r"(API_KEY|api_key|TOKEN|_SECRET|ANTHROPIC|OPENAI)", re.IGNORECASE)
_LLM_RE = re.compile(r"\b(llm|ChatAnthropic|ChatOpenAI|get_llm|query_llm|langchain)\b")
_SCHEMA_DB_RE = re.compile(r"schema_db|\.pkl")
_SCHEMA_DIR = Path(__file__).resolve().parent.parent / "biomni" / "tool" / "schema_db"


def _top_imports(src: str) -> set[str]:
    """The top-level package names a piece of source imports."""
    out: set[str] = set()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return out
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            out.add(node.module.split(".")[0])
    return out


def _has(pkg: str) -> bool:
    if pkg in _STDLIB or pkg in ("biomni", "biomni_ui"):
        return True
    try:
        return importlib.util.find_spec(pkg) is not None
    except (ImportError, ValueError, AttributeError):
        return False


def analyse(fn: Any, module_imports: set[str]) -> dict[str, Any]:
    """Static check of one tool function: its status and the reasons it may not run here."""
    try:
        src = inspect.getsource(fn)
    except (OSError, TypeError):
        return {"status": UNKNOWN, "missing": [], "needs": []}
    imports = _top_imports(src) | module_imports
    missing = sorted(p for p in imports if not _has(p))
    needs = []
    blocked = False  # a missing local file or command-line program: the tool cannot run as it is
    if _LLM_RE.search(src):
        needs.append("calls an LLM (slower, and one extra model call)")
    if _KEY_RE.search(src) and "os.environ" in src or "getenv" in src and _KEY_RE.search(src):
        needs.append("needs an API key")
    if _SCHEMA_DB_RE.search(src):
        wanted = re.findall(r"""schema_db['"],\s*['"]([\w.\-]+\.pkl)""", src)
        absent = [w for w in wanted if not (_SCHEMA_DIR / w).exists()]
        if absent:
            needs.append("needs a local interface-description file (.pkl) that is missing: " + ", ".join(absent))
            blocked = True
        elif not wanted:  # the file name is built elsewhere (a helper that makes the .pkl from the data lake on first use): not a block
            needs.append("builds a cache from the data lake on first use (slower)")
    exes = sorted({m for m in re.findall(r"""['"]([a-zA-Z0-9_.+-]+)['"]\s*[,\]]""", src) if shutil.which(m)}) if "subprocess" in src else []
    if "subprocess" in src and not exes:
        needs.append("calls an external command-line program (usually not installed on this machine)")
        blocked = True
    if missing:
        status = MISSING
    elif blocked:
        status = RESTRICTED
    elif needs:
        status = CONDITIONAL
    else:
        status = AVAILABLE
    return {"status": status, "missing": missing, "needs": needs}


def scan() -> list[dict[str, Any]]:
    """Analyse every stock tool description. Slow: it imports each tool module once."""
    import glob
    import os

    rows = []
    base = Path(importlib.import_module("biomni.tool").__file__).parent
    for f in sorted(glob.glob(str(base / "tool_description" / "*.py"))):
        m = os.path.basename(f)[:-3]
        if m.startswith("__"):
            continue
        desc = importlib.import_module(f"biomni.tool.tool_description.{m}").description
        try:
            mod = importlib.import_module(f"biomni.tool.{m}")
            mod_imports = _top_imports(inspect.getsource(mod).split("\ndef ", 1)[0])
        except Exception as e:
            for d in desc:
                rows.append({"name": d["name"], "module": m, "description": d.get("description", ""), "status": UNIMPORTABLE, "missing": [], "needs": [f"{type(e).__name__}"]})
            continue
        for d in desc:
            fn = getattr(mod, d["name"], None)
            info = analyse(fn, mod_imports) if callable(fn) else {"status": NOT_FOUND, "missing": [], "needs": []}
            rows.append({"name": d["name"], "module": m, "description": d.get("description", ""), **info})
    return rows


def load(path: Path, max_age: float = 24 * 3600) -> list[dict[str, Any]]:
    """The cached scan when it is fresh and uses the current status tokens; otherwise a new scan, written back to the cache."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = data["rows"]
        if time.time() - data["at"] < max_age and not any(r.get("status") in LEGACY_STATUS for r in rows):
            return rows
    except Exception:
        pass
    rows = scan()
    path.write_text(json.dumps({"at": time.time(), "rows": rows}, ensure_ascii=False), encoding="utf-8")
    return rows


def summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        out[r["status"]] = out.get(r["status"], 0) + 1
    return out
