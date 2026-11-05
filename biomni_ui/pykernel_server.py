"""The process behind the `python` tool: one long-lived interpreter whose variables and imports survive from step to step.

Started by `biomni_ui.pykernel`. Protocol: one JSON object per line on stdin ({"id", "code"}) and on stdout ({"id", "out", "err",
"secs"}); whatever the code prints is captured, so it can never corrupt the protocol. The heavy libraries are imported in a
background thread right after start, so the first real step does not pay for them. When the parent goes away the pipe closes
and the process ends.
"""

from __future__ import annotations

import ast
import contextlib
import importlib
import io
import json
import os
import sys
import threading
import time
import traceback

ROOT = os.environ.get("BIOMNI_KERNEL_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

PRELOAD = ("numpy", "pandas", "matplotlib.pyplot", "scipy.stats", "biomni_ui.lit", "biomni_ui.web", "biomni_ui.dbtools", "biomni_ui.report",
           "biomni.tool.database", "biomni.tool.genomics", "biomni.tool.pharmacology")
G: dict = {"__name__": "__main__"}


def _bind_model() -> None:
    """The stock `query_*` tools ask a model to turn a question into a request; point them at ours (the same binding the app process has)."""
    try:
        from biomni_ui import chatgpt_api, fast_tools

        fast_tools.route_tool_llm(lambda: chatgpt_api.ChatCodexAPI(reasoning_effort="medium", native_search=False))
    except Exception:
        pass


def find_tools(query: str, limit: int = 8) -> None:
    """List the specialist tools that match English keywords, with import path and parameters."""
    from biomni_ui import biomni_tools

    print(biomni_tools.find_tools(query, limit))


G["find_tools"] = find_tools


def _preload() -> None:
    for name in PRELOAD:
        try:
            importlib.import_module(name)
        except Exception:
            pass
    _bind_model()


def _run(code: str) -> None:
    tree = ast.parse(code, mode="exec")
    last = ast.Expression(tree.body.pop().value) if tree.body and isinstance(tree.body[-1], ast.Expr) else None
    exec(compile(tree, "<step>", "exec"), G)
    if last is not None:
        value = eval(compile(last, "<step>", "eval"), G)
        if value is not None:
            print(repr(value))


def main() -> None:
    proto = sys.stdout
    os.chdir(os.environ.get("BIOMNI_KERNEL_CWD") or ROOT)
    threading.Thread(target=_preload, daemon=True).start()
    proto.write(json.dumps({"ready": True}) + "\n")
    proto.flush()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except ValueError:
            continue
        out, err = io.StringIO(), io.StringIO()
        t0 = time.time()
        error = ""
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                _run(str(req.get("code") or ""))
        except SystemExit:
            error = "The code called exit(); it was ignored."
        except BaseException as e:  # a failing step is reported to the model, which fixes it; the session stays alive
            tb = e.__traceback__
            while tb is not None and tb.tb_frame.f_code.co_filename != "<step>":  # show the step's own lines, not this file's
                tb = tb.tb_next
            error = "".join(traceback.format_exception(type(e), e, tb or e.__traceback__)).strip()
        proto.write(json.dumps({"id": req.get("id"), "out": out.getvalue(), "err": (err.getvalue() + ("\n" + error if error else "")).strip(),
                                "secs": round(time.time() - t0, 2)}, ensure_ascii=False) + "\n")
        proto.flush()


if __name__ == "__main__":
    main()
