"""Client side of the persistent Python session (the `python` tool): spawn, run a step with a timeout, keep one per conversation.

The official app keeps a Jupyter kernel per task; a fresh `python - <<EOF` per step re-imports pandas / the Biomni tool modules
every time (5-6 s each in our measurements). Here the first step starts the interpreter and every later step reuses its imports
and variables. A step that runs too long, or a cancelled task, kills the interpreter; the next step starts a fresh one and the
reply says the variables are gone.
"""

from __future__ import annotations

import atexit
import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable

SERVER = Path(__file__).resolve().parent / "pykernel_server.py"
OUTPUT_HEAD, OUTPUT_TAIL = 3500, 2500
MAX_KERNELS = 4
IDLE_SECONDS = 30 * 60


def _truncate(text: str) -> str:
    if len(text) <= OUTPUT_HEAD + OUTPUT_TAIL:
        return text
    return text[:OUTPUT_HEAD] + f"\n... ({len(text) - OUTPUT_HEAD - OUTPUT_TAIL} characters omitted in the middle) ...\n" + text[-OUTPUT_TAIL:]


class Kernel:
    def __init__(self, cwd: Path) -> None:
        scripts = Path(sys.prefix) / "Scripts" / "python.exe"
        exe = str(scripts) if scripts.is_file() else sys.executable
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1", "NO_PROXY": "localhost,127.0.0.1,::1", "MPLBACKEND": "Agg",
               "MATPLOTLIBRC": str(Path(__file__).resolve().parent / "mpl"), "BIOMNI_KERNEL_CWD": str(cwd),
               "BIOMNI_KERNEL_ROOT": str(Path(__file__).resolve().parent.parent)}
        self.proc = subprocess.Popen([exe, "-X", "utf8", str(SERVER)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                     text=True, encoding="utf-8", errors="replace", cwd=str(cwd), env=env, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.lines: queue.Queue[dict] = queue.Queue()
        self.dead = False
        self.started = time.time()
        self.last_used = time.time()
        self.steps = 0
        self._next = 0
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        try:
            for line in self.proc.stdout:  # type: ignore[union-attr]
                try:
                    self.lines.put(json.loads(line))
                except ValueError:
                    continue
        except Exception:
            pass
        self.lines.put({"closed": True})

    def alive(self) -> bool:
        return not self.dead and self.proc.poll() is None

    def kill(self) -> None:
        self.dead = True  # poll() can still say "running" for a moment after kill()
        try:
            self.proc.kill()
        except Exception:
            pass

    def run(self, code: str, timeout: int, cancel: Callable[[], bool]) -> str:
        self.last_used = time.time()
        self._next += 1
        rid = self._next
        try:
            self.proc.stdin.write(json.dumps({"id": rid, "code": code}, ensure_ascii=False) + "\n")  # type: ignore[union-attr]
            self.proc.stdin.flush()  # type: ignore[union-attr]
        except Exception:
            self.kill()
            return "The Python session has ended. Run again (the earlier variables are gone)."
        t0 = time.time()
        while True:
            if cancel():
                self.kill()
                return "(cancelled)"
            if time.time() - t0 > timeout:
                self.kill()
                return f"(this step took longer than {timeout} seconds, so the Python session was restarted and the earlier variables are gone. Split the task into smaller steps, or use a faster approach.)"
            try:
                msg = self.lines.get(timeout=0.3)
            except queue.Empty:
                continue
            if msg.get("closed"):
                return "The Python session exited unexpectedly (possibly out of memory or a code crash), and the earlier variables are gone. Run again."
            if msg.get("ready"):
                continue
            if msg.get("id") == rid:
                self.steps += 1
                self.last_used = time.time()
                text = (msg.get("out") or "").rstrip()
                err = (msg.get("err") or "").strip()
                if err:
                    text = (text + "\n" if text else "") + err
                return _truncate(text) or "(no output)"


class Pool:
    """One kernel per conversation (None = a throw-away one that the caller closes), a few at a time, idle ones are retired."""

    def __init__(self) -> None:
        self._kernels: dict[str, Kernel] = {}
        self._lock = threading.Lock()
        atexit.register(self.close_all)

    def get(self, session: str, cwd: Path) -> tuple[Kernel, bool]:
        """(kernel, True when it is a fresh one although the session had an earlier one that died)."""
        with self._lock:
            now = time.time()
            for key in [k for k, v in self._kernels.items() if not v.alive() or now - v.last_used > IDLE_SECONDS]:
                dead = self._kernels.pop(key)
                dead.kill()
                if key == session:
                    reset = True
                    break
            else:
                reset = False
            k = self._kernels.get(session)
            if k is None:
                while len(self._kernels) >= MAX_KERNELS:
                    oldest = min(self._kernels, key=lambda x: self._kernels[x].last_used)
                    self._kernels.pop(oldest).kill()
                k = Kernel(cwd)
                self._kernels[session] = k
            return k, reset

    def close(self, session: str) -> None:
        with self._lock:
            k = self._kernels.pop(session, None)
        if k:
            k.kill()

    def close_all(self) -> None:
        with self._lock:
            ks, self._kernels = list(self._kernels.values()), {}
        for k in ks:
            k.kill()


POOL = Pool()


def run(session: str, code: str, cwd: Path, cancel: Callable[[], bool] = lambda: False, timeout: int = 180) -> str:
    kernel, reset = POOL.get(session, cwd)
    text = kernel.run(code, timeout, cancel)
    if not kernel.alive():
        POOL.close(session)
    return (("(the previous Python session has ended; this is a new session, and the earlier variables are gone.)\n" if reset else "") + text)
