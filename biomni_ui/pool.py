"""Run several tasks at once: the server's own agent plus worker processes, each with its own agent.

One agent runs one task at a time (its Python session, captured output and prompt are process-wide), so tasks that overlap
need separate processes. A worker is `python -m biomni_ui.worker`: it builds its own agent, takes one job at a time over
stdin and sends every event back as a JSON line, which the server stores and streams like any other.

A conversation always goes back to the slot that ran its earlier messages, because the agent's memory of the conversation
lives in that process.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

RESTART_SECONDS = 5


class LocalSlot:
    """The server's own agent."""

    name = "local"
    ready = True
    alive = True

    def __init__(self, manager) -> None:
        self.m = manager
        self.busy = False

    def available(self) -> bool:
        return not self.busy

    def run(self, task) -> None:
        self.busy = True
        threading.Thread(target=self._go, args=(task,), daemon=True, name=f"task-{task.id}").start()

    def _go(self, task) -> None:
        try:
            self.m._run(task)
        finally:
            self.busy = False
            self.m._dispatch()

    def cancel(self, task_id: str) -> None:  # the task's own flag is what the agent loop watches
        pass

    def command(self, name: str) -> None:
        pass


class ProcSlot:
    """One worker process."""

    def __init__(self, index: int, manager, root: Path) -> None:
        self.name = f"worker-{index}"
        self.m = manager
        self.root = root
        self.proc: subprocess.Popen | None = None
        self.ready = False
        self.alive = False
        self.busy = False
        self.current = None
        self._stopping = False
        self._send_lock = threading.Lock()

    def available(self) -> bool:
        return self.alive and self.ready and not self.busy

    # -- process ------------------------------------------------------------------------------
    def start(self) -> None:
        if self._stopping:
            return
        env = {**os.environ, "BIOMNI_UI_WORKER": "1", "PYTHONIOENCODING": "utf-8", "NO_PROXY": "localhost,127.0.0.1,::1"}
        log = open(self.root / "ui_data" / f"{self.name}.log", "ab")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "biomni_ui.worker"], cwd=str(self.root), env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=log, creationflags=flags, text=True, encoding="utf-8", bufsize=1,
        )
        self.alive, self.ready = True, False
        threading.Thread(target=self._reader, args=(self.proc,), daemon=True, name=f"{self.name}-reader").start()

    def stop(self) -> None:
        self._stopping = True
        p = self.proc
        if p and p.poll() is None:
            try:
                p.stdin.close()
            except Exception:
                pass
            try:
                p.wait(timeout=5)
            except Exception:
                p.kill()

    def _send(self, obj: dict[str, Any]) -> None:
        with self._send_lock:
            assert self.proc and self.proc.stdin
            self.proc.stdin.write(json.dumps(obj, ensure_ascii=False) + "\n")
            self.proc.stdin.flush()

    # -- jobs ---------------------------------------------------------------------------------
    def run(self, task) -> None:
        self.busy, self.current = True, task
        try:
            self._send({"cmd": "task", "id": task.id, "prompt": task.prompt, "extra": task.extra, "mode": task.mode,
                        "conversation_id": task.conversation_id, "first": task.first_in_conversation})
        except Exception as e:
            self._finish(f"Could not hand the task to the worker process: {type(e).__name__}: {e}")

    def cancel(self, task_id: str) -> None:
        if self.current is not None and self.current.id == task_id:
            try:
                self._send({"cmd": "cancel", "id": task_id})
            except Exception:
                pass

    def command(self, name: str) -> None:
        if self.alive:
            try:
                self._send({"cmd": name})
            except Exception:
                pass

    def _finish(self, error: str | None = None) -> None:
        task, self.current, self.busy = self.current, None, False
        if task is not None and not task.finished:
            task.emit({"type": "error", "message": error or "The worker process ended the task without a result"})
        self.m._dispatch()

    def _reader(self, proc: subprocess.Popen) -> None:
        assert proc.stdout
        for line in proc.stdout:
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            kind = msg.get("t")
            task = self.m.get(msg.get("id", "")) if msg.get("id") else None
            if kind == "ready":
                self.ready = True
                self.m._dispatch()
            elif kind == "event" and task is not None:
                task.emit(msg["event"])
            elif kind == "draft" and task is not None:
                task.emit_draft(msg.get("text", ""))
            elif kind == "finished":
                self._finish()
        # the process is gone
        self.alive = self.ready = False
        if proc is self.proc and not self._stopping:
            if self.busy:
                self._finish("The worker process exited unexpectedly; the task was stopped")
            threading.Timer(RESTART_SECONDS, self._restart).start()

    def _restart(self) -> None:
        if not self._stopping:
            self.start()
