"""A worker process for biomni_ui.pool: builds its own agent and runs one task at a time.

Protocol: JSON lines. In (stdin): {"cmd": "task", ...} | {"cmd": "cancel", "id"} | {"cmd": "reset"} | {"cmd": "sync_skills"}.
Out (stdout): {"t": "ready"} | {"t": "event", "id", "event"} | {"t": "draft", "id", "text"} | {"t": "finished", "id"}.
Everything else the libraries print goes to stderr (the worker log), never into the protocol stream.
"""

from __future__ import annotations

import json
import os
import sys
import threading


def main() -> None:
    proto = os.fdopen(os.dup(1), "w", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr
    send_lock = threading.Lock()

    def send(obj: dict) -> None:
        with send_lock:
            proto.write(json.dumps(obj, ensure_ascii=False) + "\n")
            proto.flush()

    os.environ["BIOMNI_UI_WORKER"] = "1"
    from biomni_ui import server
    from biomni_ui.runner import Task

    mgr = server.manager

    class RemoteTask(Task):
        """The task as the agent sees it, with events and drafts sent to the server instead of stored here."""

        def __init__(self, msg: dict) -> None:
            self._cancel = threading.Event()
            super().__init__(msg["prompt"], msg["conversation_id"], None, msg.get("extra", ""), mode=msg.get("mode", "ask"))
            self.id = msg["id"]
            self.first_in_conversation = bool(msg.get("first", True))

        @property
        def cancel_requested(self) -> bool:
            return self._cancel.is_set()

        @cancel_requested.setter
        def cancel_requested(self, value: bool) -> None:
            self._cancel.set() if value else self._cancel.clear()

        def emit(self, event: dict) -> None:
            with self._cond:
                self.events.append({**event, "seq": len(self.events)})  # the audit reads what the tools printed
                if event["type"] in ("done", "error", "cancelled"):
                    self.finished = True
            send({"t": "event", "id": self.id, "event": event})

        def emit_draft(self, text: str) -> None:
            send({"t": "draft", "id": self.id, "text": self.shown_draft(text)})  # the server only relays it

    state = {"current": None, "reset": False}

    def run_job(msg: dict) -> None:
        task = RemoteTask(msg)
        state["current"] = task
        try:
            if state["reset"]:
                mgr.reset_agent()
                state["reset"] = False
            agent = mgr.agent()
            agent.llm = server._build_llm(search=True)  # the model and effort chosen in the settings right now
            mgr._run(task)
        except Exception as e:
            task.emit({"type": "error", "message": f"{type(e).__name__}: {e}"})
        finally:
            state["current"] = None
            send({"t": "finished", "id": task.id})

    try:
        mgr.agent()
    except Exception as e:
        print(f"worker could not build its agent: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
    send({"t": "ready"})

    for line in sys.stdin:  # ends when the server closes the pipe (or dies)
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        cmd = msg.get("cmd")
        if cmd == "task":
            threading.Thread(target=run_job, args=(msg,), daemon=True).start()
        elif cmd == "cancel":
            t = state["current"]
            if t is not None and t.id == msg.get("id"):
                t.cancel_requested = True
        elif cmd == "reset":
            state["reset"] = True
        elif cmd == "sync_skills":
            try:
                server.skills.sync_agent(mgr.agent())
            except Exception as e:
                print(f"skill sync failed: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
