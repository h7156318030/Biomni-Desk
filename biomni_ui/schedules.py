"""Scheduled research tasks: a saved question that runs by itself at a set time.

A job is {id, name, prompt, project_id, schedule, enabled, next_run, last_run, last_task_id, last_conversation_id, last_status}.
Schedules are either "every N minutes" (5 minutes to 31 days) or "daily at HH:MM" in this computer's local time.

The scheduler runs inside the Biomni-Desk server, so a job runs only while the server is open. When a job is due but the agent
is busy or not ready, it is not dropped: the check is repeated a minute later. Each run starts in auto mode (no questions),
and its results are saved in the normal conversation history.
"""

from __future__ import annotations

import json
import re
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

MIN_MINUTES = 5
MAX_MINUTES = 31 * 24 * 60
RETRY_SECONDS = 60
_TIME = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


class SkipRun(Exception):
    """Raised by the start function when a run cannot start now (agent busy); the job is retried later."""


def validate(kind: str, minutes: int | None, at: str | None) -> dict[str, Any]:
    if kind == "every":
        if minutes is None or not (MIN_MINUTES <= int(minutes) <= MAX_MINUTES):
            raise ValueError(f"The interval must be between {MIN_MINUTES} minutes and 31 days.")
        return {"kind": "every", "minutes": int(minutes)}
    if kind == "daily":
        if not at or not _TIME.match(at):
            raise ValueError("The daily time must look like 08:30.")
        return {"kind": "daily", "time": at}
    raise ValueError("The schedule must be 'every' or 'daily'.")


def next_after(schedule: dict[str, Any], now: float) -> float:
    """The next run time after `now`."""
    if schedule["kind"] == "every":
        return now + schedule["minutes"] * 60
    hour, minute = (int(x) for x in schedule["time"].split(":"))
    local = time.localtime(now)
    candidate = time.mktime((local.tm_year, local.tm_mon, local.tm_mday, hour, minute, 0, 0, 0, -1))
    if candidate <= now:
        candidate += 24 * 3600  # DST changes are rare enough that this is accepted
    return candidate


class ScheduleStore:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            return json.loads(self.path.read_text(encoding="utf-8")).get("jobs", [])
        except (OSError, ValueError):
            return []

    def _write(self, jobs: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"jobs": jobs}, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return self._read()

    def get(self, job_id: str) -> dict[str, Any] | None:
        return next((j for j in self.list() if j["id"] == job_id), None)

    def create(self, name: str, prompt: str, project_id: str | None, schedule: dict[str, Any], enabled: bool = True, now: float | None = None) -> dict[str, Any]:
        now = time.time() if now is None else now
        job = {
            "id": uuid.uuid4().hex[:10],
            "name": name.strip() or prompt.strip()[:40],
            "prompt": prompt.strip(),
            "project_id": project_id or "quick",
            "schedule": schedule,
            "enabled": bool(enabled),
            "created": now,
            "next_run": next_after(schedule, now) if enabled else None,
            "last_run": None,
            "last_task_id": None,
            "last_conversation_id": None,
            "last_status": "",
        }
        with self._lock:
            jobs = self._read()
            jobs.append(job)
            self._write(jobs)
        return job

    def update(self, job_id: str, name: str, prompt: str, project_id: str | None, schedule: dict[str, Any], enabled: bool, now: float | None = None) -> dict[str, Any] | None:
        now = time.time() if now is None else now
        with self._lock:
            jobs = self._read()
            job = next((j for j in jobs if j["id"] == job_id), None)
            if job is None:
                return None
            job.update(name=name.strip() or prompt.strip()[:40], prompt=prompt.strip(), project_id=project_id or "quick", schedule=schedule, enabled=bool(enabled))
            job["next_run"] = next_after(schedule, now) if enabled else None
            self._write(jobs)
            return job

    def delete(self, job_id: str) -> bool:
        with self._lock:
            jobs = self._read()
            kept = [j for j in jobs if j["id"] != job_id]
            if len(kept) == len(jobs):
                return False
            self._write(kept)
            return True

    def mark(self, job_id: str, **fields: Any) -> None:
        with self._lock:
            jobs = self._read()
            for j in jobs:
                if j["id"] == job_id:
                    j.update(fields)
            self._write(jobs)

    def due(self, now: float) -> list[dict[str, Any]]:
        return [j for j in self.list() if j.get("enabled") and j.get("next_run") and j["next_run"] <= now]


def run_due(store: ScheduleStore, start: Callable[[dict[str, Any]], Any], ready: Callable[[], bool], now: float | None = None) -> list[str]:
    """Start every due job the agent can take now. Returns the ids started. Jobs that cannot start are retried in a minute."""
    now = time.time() if now is None else now
    if not ready():
        return []
    started: list[str] = []
    for job in store.due(now):
        try:
            task = start(job)
        except SkipRun as e:
            store.mark(job["id"], last_status=f"skipped: {str(e)[:120]}", next_run=now + RETRY_SECONDS)
            continue
        except Exception as e:  # a failed start must not stop the other jobs; it is shown on the schedule page
            store.mark(job["id"], last_status=f"failed: {type(e).__name__}: {str(e)[:120]}", last_run=now, next_run=next_after(job["schedule"], now))
            continue
        store.mark(
            job["id"],
            last_status="started",
            last_run=now,
            last_task_id=getattr(task, "id", None),
            last_conversation_id=getattr(task, "conversation_id", None),
            next_run=next_after(job["schedule"], now),
        )
        started.append(job["id"])
    return started


def loop(store: ScheduleStore, start: Callable[[dict[str, Any]], Any], ready: Callable[[], bool], stop: threading.Event, interval: float = 30.0) -> None:
    """Background loop used by the server: checks for due jobs every `interval` seconds until `stop` is set."""
    while not stop.is_set():
        try:
            run_due(store, start, ready)
        except Exception:  # the loop keeps running; errors are visible through the job status on the next check
            pass
        stop.wait(interval)
