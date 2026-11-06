"""Run one A1 task in a background thread and expose its progress as an ordered event log."""

from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from biomni_ui import audit, chat_api, clinical, codex_llm, effort, files, llm_calls, native_agent, research, scout, workdir, worklog
from biomni_ui import effort as effort_levels
from biomni_ui.events import message_to_events
from biomni_ui.store import Store

HEARTBEAT_SECONDS = 15


def _receipt_count(work: Path) -> int:
    from biomni_ui import receipts

    try:
        return receipts.count(work)
    except Exception:
        return 0


def _write_task_qc(work: Path, start: int, answer: str, seen: str) -> str | None:
    """Save this task's QC summary: failed calls with no later success, and specifics or identifiers the answer uses that the tool output lacks.

    Returns the relative path of the saved file, or None if it could not be written. The task itself never depends on this.
    """
    from biomni_ui import receipts

    try:
        mine = receipts.read_all(work)[start:]
        unverified = [item["text"] for item in audit.ungrounded(answer, seen)]
        unsupported = audit.unsupported(answer, seen)
        return receipts.write_qc(work, receipts.qc_summary(mine, unverified, unsupported))
    except Exception:
        return None

# Appended to every task: citations the UI can check, and a fixed answer layout.
CITE_HINT = (
    "Citation rule: when the final answer cites literature or data sources, write the PMID, DOI or full URL right after the sentence it supports. "
    "Cite only sources that actually appear in the tool output. A conclusion with no source gets no source, and never invent a PMID, DOI or URL from memory."
    ""
)

FORMAT_HINT = (
    "How to work: first call tools with <execute> to do the task, and answer only after you have the results. "
    "For a name you do not recognise (a company, product, abbreviation or person), do not guess that it is a gene or anything else, and do not ask the user to supply more. "
    "First search the web to find out what it refers to, then choose tools. "
    "In the first web search, use only the name itself (for example \"Example Bio\"). Do not add words such as \"company\" or \"clinical trial\": a Chinese name may be split into single characters and match dictionary entries. "
    "Before you say something cannot be found, try at least three approaches, including the English name, the Chinese name and aliases. "
    "Do not say \"could not verify\" without having run any operation. Say it only after a real attempt has failed, and state what you tried.\n"
    "For live information (news, companies, products, regulations, weather) you may use your built-in web search directly: search and answer in the same reply, and put the source links in the answer. Write <execute> when you need to read full web pages, query databases, or calculate and run statistics.\n"
    "Act in your first reply (a web search, or <execute> to search, query or calculate). Do not apologise first, do not ask \"shall I look it up?\", do not start with \"I cannot ...\", and do not write only a plan. If a search fails, retry with another method.\n"
    "Factual conclusions come from the searches and databases you actually called in this round, and you state their sources.\n"
    "Real-time information (weather, news, prices, fixtures, and anything \"latest\" or \"current\") must be searched online. Do not answer from memory, and do not only say \"I will look it up\": write <execute> in the same reply.\n"
    "\n"
    "The first line of every <execute> block is a one-line comment giving the step's title: what the step does, in no more than 30 words (for example `# Look up ClinVar pathogenic variants for TP53`).\n"
    "After saving or downloading a file, check it in the next step: the file exists, its size is not zero, and its first lines read correctly. If a check fails, retry or switch source. Do not say \"done\" without checking.\n"
    "\n"
    "The answer (inside <solution>, in Markdown, in the user's language): the first paragraph gives the conclusion directly, in no more than three sentences, without repeating the question. Organise the rest by task type; do not use one template for everything:\n"
    "- Facts, literature, databases: key points one by one, each followed directly by its source (PMID, DOI or URL); a table when comparing.\n"
    "- Data analysis: what was done (data, methods, parameters), then results (key numbers, chart file names), then the conclusion, then caveats (sample size, quality control, assumptions).\n"
    "- Designs and plans (primers, sgRNA, experiments, clinical trials): the recommended plan and key parameters, then the rationale, then the risks and what needs experimental validation.\n"
    "- Calculations and simple questions: the answer directly, with the necessary derivation.\n"
    "Give sources only when the answer uses external sources, and after each source give the query date or the date of the material. "
    "Be objective and direct: state facts, and note sources and dates. "
    "For name lookups, an entity name in the search results must match the name the user gave (or be clearly an alias of it) before you use it. Exclude companies, genes or drugs with similar but different names, and go by the user's own words. "
    "Do not paste code into the answer, and do not write process narration such as \"I will ...\"."
)


_WEEKDAYS = "一二三四五六日"
_WEEKDAYS_EN = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def workspace_line(work: "Path | None" = None) -> str:
    """Where files live. The official app has a fixed layout and its first step is an `ls`; without this the model guesses paths."""
    try:
        from pathlib import Path

        from biomni.config import default_config

        up = Path(default_config.path) / "uploads"
        names = sorted((x.name for x in up.iterdir() if x.is_file()), key=str.lower)[:15] if up.is_dir() else []
        listing = ", ".join(names) if names else "(none at the moment)"
        return (
            f"File locations: files the user uploaded are in {up} (currently: {listing}). Treat them as read-only source material. The current working directory is {work or Path.cwd()}; save every result file you generate there "
            "(each conversation has its own folder, and the page's Results panel shows the new files saved here). execution_trace in this folder records each step's code, output and sources automatically; you do not write it. "
            "When the question mentions \"the uploaded / earlier / this file\", or you are unsure where a file is, first list the folder with os.listdir. Do not guess paths."
        )
    except Exception:
        return ""


def today_line() -> str:
    """The model has no clock; without this it invents a date for "本月" searches and for the 查询日期 line of its answer."""
    now = time.localtime()
    return f"Today's date is {now.tm_year}-{now.tm_mon:02d}-{now.tm_mday:02d} ({_WEEKDAYS_EN[now.tm_wday]}). Use this date for any time range such as \"recent\", \"this month\" or \"this year\"; when the answer gives a search or query date, it must be this date, not a date from memory."


def answer_language(question: str) -> str:
    """The instruction that fixes the language of the answer: the language the question is written in. A question with Chinese
    characters gets a Chinese answer; anything else gets English. Sent last, so it is the final word on the language."""
    if re.search(r"[一-鿿]", question or ""):
        return "Answer language: Chinese (简体中文). Write the whole answer in Chinese, including headings and table labels; keep names, codes and identifiers as they appear in the sources."
    return "Answer language: English. Write the whole answer in English, including headings and table labels; keep names, codes and identifiers as they appear in the sources."


# A model sometimes answers "could not verify" without having run a single query. Detect that and ask once more.
REFUSAL_RE = re.compile(r"未能|无法(?:核实|查询|检索|获取|确认|可靠)|没有取得|未执行|没有执行|不提供未经核实|could not verify|unable to (?:verify|confirm|find|retrieve)|not retrieved|did not (?:run|execute)|no (?:search|query|lookup) (?:was )?(?:run|executed|performed)", re.I)
NUDGE = (
    "You gave an answer without running a single query. First call the tools with <execute> and do the search (if it fails, read the error and retry another way), "
    "and only then give the answer in the required format. Say that something could not be verified only after you really tried and failed."
)

_OPEN_STEP = re.compile(r"\[ \]")
_HEDGE = re.compile(r"没有实际|还没有|尚未|未能|无法|不能(?:据此|判断|确认)|未执行|没有执行|没有取得|不提供未经核实|no (?:actual|real) (?:results?|data)|not (?:yet|executed|run)|could not|cannot (?:confirm|judge|determine)|unable to|not retrieved", re.I)


# "I could not find it / please tell me X": fine after real effort, not after one lookup with the first guess of what the name means
_GIVE_UP = re.compile(r"请(?:你|您)?(?:提供|告知|补充|确认|给出)|无法(?:明确|确认|对应|判断)|未(?:找到|检出|检索到)|没有(?:找到|检索到|查到|匹配)|查不到|找不到|please (?:provide|tell|supply|confirm|give)|could not (?:identify|confirm|determine|find)|cannot (?:find|identify)|no (?:match|results?) found|not found", re.I)
MIN_ATTEMPTS = 3


def premature(answer: str, code_steps: int, plan: list[dict] | None) -> str:
    """Why this answer should not be accepted yet ("" = accept). Judged on behaviour, not on wording.

    - nothing was executed and the answer is short and hedging ("no results yet, cannot judge");
    - the checklist still has open steps and the answer is little more than that checklist.
    """
    text = (answer or "").strip()
    if not text:
        return ""
    open_steps = [x["text"] for x in (plan or []) if x.get("status") == "todo"]
    if code_steps == 0 and (REFUSAL_RE.search(text) or (len(text) < 300 and _HEDGE.search(text))):
        return "answered \"not found / cannot judge\" without running any operation"
    if code_steps == 0 and open_steps and len(text) < 600:
        return f"gave a final answer without running any operation, while {len(open_steps)} planned steps were still open"
    if _OPEN_STEP.search(text) and len(text) < 1500:  # the "answer" is the checklist itself, still unticked
        return "used the unticked plan checklist as the final answer"
    if code_steps < MIN_ATTEMPTS and text.lstrip().startswith(("未经检索核实", "Not verified by a search")):  # fell back to memory after a try or two
        return f"only tried {code_steps} approaches before answering from model memory"
    if 1 <= code_steps < MIN_ATTEMPTS and len(text) < 900 and _GIVE_UP.search(text) and len(re.findall(r"https?://", text)) < 2:  # an answer with sources is a finding, even a negative one
        return f"only tried {code_steps} approaches before saying \"not found / could not confirm\" or asking the user for more information"
    return ""


GIVE_UP_NUDGE = (
    "You have tried only a few approaches. Do not stop now, and do not conclude \"not found\". First work out how to confirm it yourself and retry (use ask_user only when the choice would really change the conclusion):\n"
    "1. For a name you do not recognise, first search the web (web_search) to find out whether it is a gene, protein, company, institution, product or person. A name may not be a standard gene symbol.\n"
    "2. Once you know what it means, retry with suitable tools and forms: the Chinese name, the English name, aliases, company or product codes. Read the pages you found (read_webpage) when needed, or use deep_research.\n"
    "3. Try at least three different search methods. Only when all of them fail may you say it was not found, and then list what you tried and what you found."
)


def nudge_text(plan: list[dict] | None, reason: str = "") -> str:
    if reason.startswith("only tried"):
        return GIVE_UP_NUDGE
    open_steps = [x["text"] for x in (plan or []) if x.get("status") == "todo"]
    if open_steps:
        return ("These plan steps are not finished yet: " + "; ".join(open_steps[:5]) + ". Continue: call the tools with <execute> to complete them (if one fails, read the error and retry another way), "
                "tick each step in the plan as you finish it, and give the final answer in <solution> only when all of them are done.")
    return NUDGE


TERMINAL = {"done": "done", "error": "error", "cancelled": "cancelled"}


class Busy(RuntimeError):
    """Another task is still running (A1 holds one conversation state at a time)."""


def _loop_target(llm: Any) -> tuple[str, dict[str, Any] | None] | None:
    """(model name, chat-endpoint parameters, or None for the ChatGPT backend) for a model object; None if it cannot run the loop."""
    from biomni_ui import chatgpt_api

    inner = getattr(llm, "_inner", llm)
    if type(inner).__name__ == "ChatCodex" and chatgpt_api.is_logged_in():
        return codex_llm.resolve_model(getattr(inner, "model", None)), None
    if type(inner).__name__ == "ChatOpenAI":
        key = getattr(inner, "openai_api_key", None)
        key = key.get_secret_value() if hasattr(key, "get_secret_value") else key
        base = getattr(inner, "openai_api_base", None)
        model = getattr(inner, "model_name", None) or getattr(inner, "model", None)
        if key and base and model:
            return str(model), {"base_url": str(base), "api_key": str(key), "extra": dict(getattr(inner, "extra_body", None) or {})}
    return None


class Task:
    def __init__(self, prompt: str, conversation_id: str, store: Store | None = None, extra: str = "", mode: str = "ask",
                 agent: dict[str, Any] | None = None, tools_off: set[str] | None = None):
        self.id = uuid.uuid4().hex[:12]
        self.agent = dict(agent or {})  # the agent profile the task runs with (model, effort, instructions); empty means the app's current settings
        self.tools_off = set(tools_off or ())  # optional tools switched off for this task (profile and project choices)
        self.mode = mode if mode in ("plan", "ask", "auto") else "ask"
        self.allow_ask = self.mode == "ask"  # only the ask mode lets the agent stop and ask the user mid-task
        self.prompt = prompt
        # What the agent actually receives: the question plus any approved plan / clarifications.
        body = f"{prompt}\n\n{extra}".strip() if extra else prompt
        plain = os.environ.get("BIOMNI_UI_PLAIN_PROMPT") == "1"  # experiment: send the question untouched
        self.agent_prompt = body if plain else "\n\n".join(x for x in (body, CITE_HINT, FORMAT_HINT, workspace_line(), today_line()) if x)
        self.conversation_id = conversation_id
        self.extra = extra
        # The quick lane keeps no agent memory, so it only opens a conversation (follow-ups need the agent's thread).
        self.first_in_conversation = not (store and store.task_count(conversation_id))
        self.events: list[dict[str, Any]] = []
        self.finished = False
        self.cancel_requested = False
        self.draft_as_answer = False  # set by the lanes and the general loop, whose drafts are plain prose
        self._store = store
        self._cond = threading.Condition()
        self.draft: str = ""  # what the model is writing right now: shown live, never stored
        self._draft_ver = 0
        if store:
            store.create_task(self.id, conversation_id, prompt)

    def emit(self, event: dict[str, Any]) -> None:
        with self._cond:
            event = {**event, "seq": len(self.events), "ts": time.time()}
            self.events.append(event)
            if self._store:
                self._store.add_event(self.id, event)
                if event["type"] in TERMINAL:
                    self._store.set_status(self.id, TERMINAL[event["type"]])
            if event["type"] in TERMINAL:
                self.finished = True
            self._cond.notify_all()

    def shown_draft(self, text: str) -> str:
        """A lane or the general loop writes plain prose (no tags): it is shown as the answer being written, not as thinking."""
        if self.draft_as_answer and "<execute>" not in text and "<solution>" not in text and text.strip() and not text.lstrip().startswith(("{", "[")):
            _, text = native_agent.split_preambles(text)  # the announcement before the result is not part of the answer being written
            return "<solution>" + text
        return text

    def emit_draft(self, text: str) -> None:
        text = self.shown_draft(text)
        with self._cond:
            self.draft = text
            self._draft_ver += 1
            self._cond.notify_all()

    def stream(self, start: int = 0) -> Iterator[dict[str, Any] | None]:
        """Yield events from `start`; yield None as a heartbeat while waiting. Live drafts are interleaved (no `seq`)."""
        i = start
        seen_draft = self._draft_ver
        while True:
            with self._cond:
                if i >= len(self.events) and not self.finished and self._draft_ver == seen_draft:
                    self._cond.wait(timeout=HEARTBEAT_SECONDS)
                batch = self.events[i:]
                finished = self.finished
                draft, ver = self.draft, self._draft_ver
            if batch:
                yield from batch
                i += len(batch)
            elif finished:
                return
            elif ver != seen_draft:
                seen_draft = ver
                # an answer being written keeps its <solution> marker and a longer window; code and thinking show only their tail
                text = draft[-6000:] if draft.startswith("<solution>") and len(draft) <= 6000 else ("<solution>" + draft[-6000:] if draft.startswith("<solution>") else draft[-1500:])
                yield {"type": "draft", "text": text}
            else:
                yield None


def _tool_names(tools: Any) -> list[str]:
    names = []
    for t in tools or []:
        names.append(t.get("name", str(t)) if isinstance(t, dict) else str(t))
    return names


def _clean_fallback(text: str) -> str:
    text = re.sub(r"<execute>.*?</execute>", "", text, flags=re.DOTALL)
    text = re.sub(r"<observation>.*?</observation>", "", text, flags=re.DOTALL)
    return re.sub(r"\n\s*\n", "\n\n", text).strip()


class Manager:
    def __init__(self, agent_factory, store: Store | None = None):
        self._factory = agent_factory
        self.store = store
        self.fast_routes_enabled = lambda: os.environ.get("BIOMNI_UI_CLINICAL", "1") != "0"  # server may replace it with a setting
        self.write_llm_factory = None  # medium effort: writing a summary from material already gathered needs less thinking than the user's top setting
        self.fast_llm_factory = None  # a low-effort model for short JSON jobs (planning, gap-finding)
        self._agent = None
        self._agent_error: str | None = None
        self._agent_lock = threading.Lock()
        self._tasks: dict[str, Task] = {}
        self._current: Task | None = None
        self._start_lock = threading.Lock()
        # Several tasks at once: the server's own agent plus worker processes (see pool.py). Without workers it is the old one-at-a-time.
        self._local = None
        self._procs: list = []
        self._pending: list[Task] = []
        self._affinity: dict[str, Any] = {}  # conversation -> the slot holding its memory
        self._sched_lock = threading.RLock()
        self._native = native_agent.Conversations()
        self.roots: list[Path] = [Path.cwd()]

    @property
    def agent_ready(self) -> bool:
        return self._agent is not None

    @property
    def agent_error(self) -> str | None:
        return self._agent_error

    @property
    def busy(self) -> bool:
        return any(not t.finished for t in list(self._tasks.values())) if self._procs else self._current is not None and not self._current.finished

    def running_in(self, conversation_id: str) -> bool:
        return any(not t.finished and t.conversation_id == conversation_id for t in list(self._tasks.values()))

    def start_workers(self, n: int, root: Path) -> None:
        from biomni_ui.pool import LocalSlot, ProcSlot

        self._local = LocalSlot(self)
        self._procs = [ProcSlot(i + 1, self, root) for i in range(n)]
        for slot in self._procs:
            slot.start()

    def stop_workers(self) -> None:
        for slot in self._procs:
            slot.stop()

    def _slots(self) -> list:
        return [self._local, *self._procs] if self._local is not None else []

    def _dispatch(self) -> None:
        """Give each waiting task a free slot; a conversation waits for the slot that holds its memory."""
        with self._sched_lock:
            for task in list(self._pending):
                slot = self._affinity.get(task.conversation_id)
                if slot is not None and not slot.alive:
                    slot = None  # that process died; its memory is gone
                    self._affinity.pop(task.conversation_id, None)
                if slot is None:
                    slot = next((s for s in self._slots() if s.available()), None)
                elif not slot.available():
                    slot = None  # wait for the slot that holds this conversation
                if slot is None:
                    if not getattr(task, "queued_noted", False):
                        task.queued_noted = True
                        task.emit({"type": "status", "state": "queued"})
                    continue
                self._pending.remove(task)
                self._affinity[task.conversation_id] = slot
                slot.run(task)

    def agent(self):
        with self._agent_lock:
            if self._agent is None:
                try:
                    self._agent = self._factory()
                    self._agent_error = None
                except Exception as e:
                    self._agent_error = f"{type(e).__name__}: {e}"
                    raise
                path = getattr(self._agent, "path", None)  # <workspace>/biomni_data
                if path:
                    self.roots = [Path.cwd(), Path(path).parent]
            return self._agent

    def reset_agent(self) -> None:
        """Drop the agent so the next use rebuilds it with the current configuration."""
        with self._agent_lock:
            self._agent = None
            self._agent_error = None
        for slot in self._procs:
            slot.command("reset")

    def get(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def start(self, prompt: str, conversation_id: str | None = None, extra: str = "", mode: str = "ask", agent: dict[str, Any] | None = None,
              tools_off: set[str] | None = None) -> Task:
        with self._start_lock:
            if not self._procs and self.busy:
                raise Busy("A task is already running")
            task = Task(prompt, conversation_id or uuid.uuid4().hex[:12], self.store, extra, mode=mode, agent=agent, tools_off=tools_off)
            self._tasks[task.id] = task
            self._current = task
        if self._procs:
            with self._sched_lock:
                self._pending.append(task)
            self._dispatch()
        else:
            threading.Thread(target=self._run, args=(task,), daemon=True, name=f"task-{task.id}").start()
        return task

    def cancel(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if not task or task.finished:
            return False
        task.cancel_requested = True
        with self._sched_lock:
            if task in self._pending:  # still waiting for a slot
                self._pending.remove(task)
                task.emit({"type": "cancelled"})
                return True
        for slot in self._procs:
            slot.cancel(task_id)
        return True

    def add_event(self, task_id: str, event: dict[str, Any]) -> dict[str, Any] | None:
        """Append an after-the-fact event (review, suggestions) to a finished task."""
        if not self.store or not self.store.get_task(task_id):
            return None
        event = {**event, "seq": self.store.next_seq(task_id), "ts": time.time()}
        self.store.add_event(task_id, event)
        return event

    # -- worker ---------------------------------------------------------------------------
    def _run(self, task: Task) -> None:
        try:
            task.emit({"type": "status", "state": "starting"})
            agent = self.agent()
            task.emit({"type": "status", "state": "running"})
            self._drive(agent, task)
        except Exception as e:  # surfaced to the UI as a readable error event
            task.emit({"type": "error", "message": f"{type(e).__name__}: {e}"})
        finally:
            getattr(task, "restore_effort", lambda: None)()
            llm_calls.set_draft_sink(None)

    def _artifacts(self, paths: list[str], task: Task | None = None) -> list[dict[str, Any]]:
        from biomni_ui import versions

        out, seen = [], set()
        for p in paths:
            real = files.resolve(p, self.roots)
            if real and real not in seen:
                seen.add(real)
                out.append(files.describe(real))
                if task is not None:  # keep this content as a version when it is new for the file (see versions.py)
                    try:
                        versions.record(workdir.conversation_dir(task.conversation_id), real, task.id)
                    except Exception:  # a version that cannot be kept must not hide the result
                        pass
        return out

    def _emit_step(self, task: Task):

        """task.emit, but an observation also carries the files it mentions (the saved CSV shows up in Results)."""

        from biomni_ui.events import extract_files



        def emit(ev: dict[str, Any]) -> None:

            if ev["type"] == "observation":

                given = [str(p) for p in ev.get("files") or []]  # files the step created or rewrote (found by comparing the folder), then the ones its text names

                ev = {**ev, "files": given + [p for p in extract_files(ev["text"]) if p not in given]}

                ev["artifacts"] = self._artifacts(ev["files"], task)

            task.emit(ev)

            if ev["type"] in ("code", "observation", "tool", "plan", "reasoning", "answer", "notice"):

                workdir.add_event(workdir.conversation_dir(task.conversation_id), {"task": task.id, **{k: v for k, v in ev.items() if k != "artifacts"}})



        return emit



    def _clinical_lane(self, agent, task: Task) -> bool:
        """Plain "clinical trials of <company / drug / gene / disease>" questions: fixed steps, the model only writes the summary."""
        if not (self.fast_routes_enabled() and clinical.wants_clinical(task.prompt) and task.first_in_conversation):
            return False
        task.draft_as_answer = True
        fast = None
        if self.fast_llm_factory:
            try:
                fast = self.fast_llm_factory()
            except Exception:
                fast = None
        steps = ["Search ClinicalTrials.gov by sponsor, intervention, condition and keyword", "If the name is in Chinese or gets no hits: confirm on the web what it refers to, and get its English name and product code", "Search again with the English name or code", "Look for Chinese registry number leads", "Summarise registrations, phases and status; separate registrations from results"]

        def mark(n: int) -> None:
            task.emit({"type": "plan", "steps": [{"text": t, "status": "done" if i < n else "todo"} for i, t in enumerate(steps)]})

        mark(0)
        step_emit = self._emit_step(task)
        done = {"n": 0}

        def emit(ev: dict) -> None:
            step_emit(ev)
            if ev["type"] == "observation":
                done["n"] = min(done["n"] + 1, len(steps) - 1)
                mark(done["n"])

        llm_calls.drain()
        try:
            text = clinical.run(self._writer(agent), fast, task.prompt, today_line(), emit)
        except Exception as e:
            task.emit({"type": "notice", "text": f"The clinical trial search workflow failed; switching to the agent: {type(e).__name__}: {e}"})
            return False
        for call in llm_calls.drain():
            task.emit({"type": "llm", **call})
        if task.cancel_requested:
            task.emit({"type": "cancelled"})
            return True
        mark(len(steps))
        self._remember(agent, task, text)
        task.emit({"type": "answer", "text": text, "researched": True})
        task.emit({"type": "done"})
        return True

    def _research_lane(self, agent, task: Task) -> bool:
        """Several searches in parallel, the best pages read, one cited answer. False hands the task to the agent."""
        if not research.wants_research(task.prompt):
            return False
        task.draft_as_answer = True
        context = task.extra.strip()  # the user's saved profile and standing instructions: the anchor for "who is this person"
        if self.store:
            try:
                earlier = "\n\n".join(f"Q: {q}\nA: {a[:1200]}" for q, a in self.store.recent_exchanges(task.conversation_id) if a)
                context = (context + "\n\n" + earlier).strip()
            except Exception:
                pass
        llm_calls.drain()
        info: dict = {}
        fast = None
        if self.fast_llm_factory:
            try:
                fast = self.fast_llm_factory()
            except Exception:
                fast = None
        try:
            text = research.run(self._writer(agent), task.prompt, today_line(), context, self._emit_step(task), lambda: task.cancel_requested, info, fast)
        except Exception as e:
            task.emit({"type": "notice", "text": f"The web research workflow failed; switching to the agent: {type(e).__name__}: {e}"})
            text = None
        for call in llm_calls.drain():
            task.emit({"type": "llm", **call})
        if task.cancel_requested:
            task.emit({"type": "cancelled"})
            return True
        if not text:
            return False
        self._remember(agent, task, text)
        if research.wants_report(task.prompt):
            try:
                import re as _re

                urls = _re.findall(r"https?://[^\s)\]）>]+", text)
                step = self._emit_step(task)
                charts = research.extract_charts(fast or agent.llm, task.prompt, text, info.get("material", ""))
                from biomni_ui import report as _report

                for c in charts:  # numbers that were found verbatim in the material, drawn by make_chart
                    c["file"] = _report.make_chart(c["kind"], c["labels"], c["values"], title=c["title"], ylabel=c["unit"])
                    step({"type": "code", "language": "python", "code": f'make_chart("{c["kind"]}", {c["labels"]}, {c["values"]}, title="{c["title"]}")', "elapsed": 0.5})
                    step({"type": "observation", "text": f"Chart saved: {c['file']}", "files": [], "elapsed": 0.5})
                code, msg = research.report_from_answer(task.prompt, text, urls, charts)
                step({"type": "code", "language": "python", "code": code, "elapsed": 0.1})
                step({"type": "observation", "text": msg, "files": [], "elapsed": 0.1})
            except Exception as e:
                task.emit({"type": "notice", "text": f"The report file was not generated: {type(e).__name__}: {e}"})
        task.emit({"type": "answer", "text": text, "researched": True})
        task.emit({"type": "done"})
        return True

    @staticmethod
    def _remember(agent, task: Task, text: str) -> None:
        """Put the quick exchange into the conversation's agent thread, so a follow-up question has its context."""
        try:
            from langchain_core.messages import AIMessage, HumanMessage

            config = {"configurable": {"thread_id": task.conversation_id}}
            agent.app.update_state(config, {"messages": [HumanMessage(content=task.prompt), AIMessage(content=text)]})
        except Exception:
            pass  # best effort: without it the follow-up simply starts fresh

    def _writer(self, agent):
        """The model that writes a lane's final summary: one step below the user's setting when the settings allow it."""
        if self.write_llm_factory:
            try:
                llm = self.write_llm_factory()
                if llm is not None:
                    return llm
            except Exception:
                pass
        return agent.llm

    def _skill_finder(self):
        """find_skills: the enabled skills that best match a keyword query (id and title), so the prompt carries no catalog."""
        import re

        store = getattr(self, "skill_store", None)

        def find(query: str) -> str:
            if store is None:
                return "No skill library."
            from biomni_ui import skill_find, usage

            if not skill_find.terms(query):
                return "Please give keywords."
            scored = []
            for score, item in skill_find.scored(query, store.list()):  # whole words, Chinese and English terms both ways, specific words weigh more
                bonus = usage.store().bonus("skill", str(item.get("id") or ""))  # a skill used before ranks a little higher
                scored.append((score + bonus, item))
            if not scored:
                return f"No skill in the library relates to \"{query}\". You can use Biomni functions or web search directly."
            scored.sort(key=lambda x: -x[0])
            lines = [f"- {i['id']}: {' '.join(str(i.get('title') or i['id']).split())[:40]}" for _, i in scored[:8]]
            return "Most relevant skills (load the full text with use_skill by id):" + chr(10) + chr(10).join(lines)

        return find

    def _skill_catalog(self):
        """(one line per enabled skill, a loader for the full manual): the catalog is always in the prompt, a manual only when asked for."""
        store = getattr(self, "skill_store", None)
        if store is None:
            return "", None
        try:
            items = [i for i in store.list() if i.get("enabled")]
        except Exception:
            return "", None
        def line(i: dict[str, Any]) -> str:
            title = " ".join(str(i.get("title") or i["id"]).split())[:40]
            return f"- {i['id']}: {title}"  # title only: the manual comes with use_skill, so the prompt stays small

        lines = [line(i) for i in items]

        def load(sid: str) -> str:
            full = store.get(sid)
            if not full or not full.get("enabled", True):
                return ""
            meta = {k: full.get(k, "") for k in ("title", "description", "when_to_use", "avoid", "uses")}
            from biomni_ui.skills import render_for_agent

            return render_for_agent(meta, full["body"])[:7000]

        return "\n".join(lines), load

    def _native_history(self, conversation_id: str) -> list[dict[str, Any]]:
        """What this conversation said so far. Kept in memory; after a restart it is rebuilt from the stored questions and answers,
        so a follow-up ("that earlier result") still has its context (the official app injects the history; ours must not lose it on a restart)."""
        items = self._native.get(conversation_id)
        if items:
            return items
        # the work of a task that was cut short (a stop or a restart) comes after the finished exchanges, so "continue" picks it up
        resumed = native_agent.load_resume(conversation_id)
        if not self.store:
            return resumed
        try:
            conv = self.store.get_conversation(conversation_id)
        except Exception:
            return resumed
        out: list[dict[str, Any]] = []
        for t in (conv or {}).get("tasks", []):
            answer = next((e.get("text", "") for e in t.get("events", []) if e.get("type") == "answer"), "")
            if answer:
                out.append({"type": "message", "role": "user", "content": [{"type": "input_text", "text": t["prompt"]}]})
                out.append({"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": answer[:4000]}]})
        return out[-20:] + resumed

    def _checkpoint(self, conversation_id: str, items: list[dict[str, Any]]) -> None:
        """Keep the work so far, in memory and on disk, so that a task cut short by a stop or a restart can be continued."""
        try:
            self._native.put(conversation_id, native_agent.complete_exchange(items))
            native_agent.save_resume(conversation_id, self._native.get(conversation_id))
        except Exception as e:  # keeping the work is a safety net; it must not stop the task
            print(f"could not keep the work so far: {type(e).__name__}: {e}")

    def _native_lane(self, agent, task: Task) -> bool:
        """The one agent loop: function calling with plain shell steps. False means the model cannot call tools (the task says so)."""
        from biomni_ui import chatgpt_api

        profile = task.agent or {}
        factory = getattr(self, "llm_for_profile", None)
        if factory is not None and (profile.get("model_id") or profile.get("effort")):
            agent = type("ProfileAgent", (), {"llm": factory(profile)})()  # this profile's model and effort; the default agent keeps its own
        llm = getattr(agent, "llm", None)
        inner = getattr(llm, "_inner", llm)
        chat = None  # (base_url, api_key, extra body) when the model sits on a chat-completions endpoint instead of the ChatGPT backend
        if type(inner).__name__ == "ChatCodex" and chatgpt_api.is_logged_in():
            model = codex_llm.resolve_model(getattr(inner, "model", None))
            ceiling = getattr(inner, "reasoning_effort", "high")
        elif type(inner).__name__ == "ChatOpenAI" and os.environ.get("BIOMNI_UI_CHAT_LOOP", "1") != "0":
            key = getattr(inner, "openai_api_key", None)
            key = key.get_secret_value() if hasattr(key, "get_secret_value") else key
            base = getattr(inner, "openai_api_base", None)
            model = getattr(inner, "model_name", None) or getattr(inner, "model", None)
            if not (key and base and model):
                return False
            chat = (str(base), str(key), dict(getattr(inner, "extra_body", None) or {}))
            ceiling = str(chat[2].get("reasoning_effort") or (chat[2].get("reasoning") or {}).get("effort") or "")  # what is really sent (the level picked in the page), or nothing for a model with no such setting
        else:
            return False
        task.draft_as_answer = True
        has_files = bool(re.search(r"\.(csv|tsv|xlsx?|h5ad|fa|fasta|fastq|pdf|docx|vcf|bam)\b|上传|附件|我的(?:文件|数据)|upload|attachment|my (?:file|data)", task.prompt, re.I))
        level = effort.heuristic(task.prompt, has_files)
        eff = effort.floor(ceiling)  # the level picked in the page, never below the starting tier (medium); no call on the answer path reasons less
        style_file = Path("ui_data/native_style.txt")  # lets a comparison switch styles without a restart
        style = (style_file.read_text(encoding="utf-8").strip() if style_file.exists() else "") or os.environ.get("BIOMNI_UI_NATIVE_STYLE", "biomni")
        catalog = ""  # no catalog in the prompt: the agent searches the library with find_skills and loads a manual with use_skill
        _, load_skill = self._skill_catalog()
        find_skill = self._skill_finder() if os.environ.get("BIOMNI_UI_SKILLS", "1") == "1" else None
        work = workdir.conversation_dir(task.conversation_id)  # this conversation's own folder: shell, Python session, results, trace
        receipt_start = _receipt_count(work)  # receipts are per conversation; this task's QC summary covers only the ones after this point
        from biomni_ui import environment, notes as user_notes  # the packages and R on this machine; what the user asked to keep
        project_id = self.store.conversation_project(task.conversation_id) if self.store else None  # the notes that belong to this project
        if project_id == "quick":
            project_id = None

        def permit(tool: str, call_id: str) -> str:
            """Allow or refuse one database connector call: a standing grant, or the user's answer in the chat (see permissions.py)."""
            from biomni_ui import connectors as _connectors, permissions

            return permissions.decide(tool, _connectors.group_of(tool) or tool, task.conversation_id, project_id,
                                      interactive=task.mode != "auto", emit=self._emit_step(task), cancel=lambda: task.cancel_requested)

        roles = self._roles()  # Settings: sub-agent count and effort, the image model, memory switches
        # The sub-agents' model, when Settings chooses one different from the main model (see native_agent._delegate).
        delegate_model, delegate_call = None, None
        factory = getattr(self, "subagent_llm", None)
        try:
            sub_llm = factory() if factory else None
            target = _loop_target(sub_llm) if sub_llm is not None else None
        except Exception:  # a sub-agent model that cannot be built falls back to the main model, which is visible in Settings
            target = None
        if target is not None:
            delegate_model, endpoint = target
            if endpoint is not None:
                from biomni_ui import chat_api as _chat_api

                def delegate_call(m, e, instr, its, tools, on_text=None, _ep=endpoint):
                    return _chat_api.call_chat(_ep["base_url"], _ep["api_key"], m, instr, its, tools, on_text, _ep["extra"])
        memory_on = bool(self.store.get_project_settings(project_id or "quick").get("memory_on", True)) if self.store else True  # the project's memory switch
        instructions = "\n\n".join(x for x in (native_agent.system_prompt(style, catalog), workspace_line(work), today_line(), environment.line(), user_notes.recall(task.prompt, project_id, enabled=memory_on, budget=roles.get("memory_recall_chars")),
                                                                                     worklog.block(project_id, query=task.prompt, exclude_conversation=task.conversation_id, budget=roles.get("memory_recall_chars"), enabled=memory_on)) if x)
        from biomni_ui import relevant  # the Biomni functions and skills this question calls for, as the official A1 lists its functions per task
        if relevant.enabled():
            try:
                from biomni_ui import biomni_tools

                skill_items = [s for s in self.skill_store.list()] if getattr(self, "skill_store", None) else []
                related = relevant.block(task.prompt, biomni_tools.catalog(), skill_items)
                if related:
                    instructions += "\n\n" + related
            except Exception:  # a missing list is not a reason to stop the task
                pass
        n_sub = int(roles.get("subagent_max") or 3)
        if n_sub > 1:  # the work split: independent parts run side by side, the rest stays with the main agent
            instructions += (f"\n\nSub-agents: up to {n_sub} can run at once (delegate_task). When the question has parts that do not depend on each other "
                             "(several samples, databases, papers or identifiers), start each part as a sub-agent in the same round so they run in parallel, "
                             "and keep the steps that need your own view. Use wait_subagents only when a result is needed for your next step.")
        if not task.allow_ask:
            instructions += "\n\nThis task cannot ask questions midway: where unsure, continue with the most plausible reading and state your assumption in the answer."
        if chat is None and os.environ.get("BIOMNI_UI_FUNC_SEARCH", "1") == "0":  # the old ChatGPT-only search: the model never sees our page numbers, so it cites full addresses
            instructions += "\n\nWhen citing a web page, write the full URL in the form [caption](full URL). Do not write [@N]: you cannot see those numbers."
        if (task.agent or {}).get("instructions"):  # this agent profile's own instructions
            instructions += "\n\n## Instructions of this agent profile (the user set these; follow them unless they conflict with the question)\n" + task.agent["instructions"]
        instructions += "\n\n" + answer_language(task.prompt)  # last, so the answer language follows the question
        question = f"{task.prompt}\n\n{task.extra}".strip() if task.extra else task.prompt
        emit = self._emit_step(task)

        def nudge(answer: str, steps: int):
            why = premature(answer, steps, None)
            if not why:
                return None
            return nudge_text(None, why), f"The agent {why}; it has been asked to continue."

        llm_calls.drain()
        extra_kw: dict[str, Any] = {}
        if chat is None and os.environ.get("BIOMNI_UI_FUNC_SEARCH", "1") != "0":  # our own search functions: queries and urls arrays run side by side
            extra_kw = {"tools_fn": lambda: native_agent.chat_tools_list(question)}
        if chat:
            base_url, api_key, extra_body = chat
            def light(extra: dict) -> dict:
                """The request body for the sufficiency judge: the same model at the starting tier (medium), never none. The judge decides
                whether the answer starts, so it is not allowed to think less than the answer does."""
                out = dict(extra)
                if "reasoning" in extra:
                    out["reasoning"] = {**(extra.get("reasoning") or {}), "effort": effort.FLOOR}
                if "reasoning_effort" in extra:
                    out["reasoning_effort"] = effort.FLOOR
                return out

            extra_kw = {"call": lambda m, e, instr, its, tools, on_text=None: chat_api.call_chat(base_url, api_key, m, instr, its, tools, on_text, light(extra_body) if e == "judge" else extra_body),
                        "tools_fn": lambda: native_agent.chat_tools_list(question)}
        if task.tools_off:  # optional tools this task's profile or project has switched off: they are not offered to the model
            off = set(task.tools_off)
            base_tools = extra_kw.get("tools_fn") or native_agent.active_tools
            extra_kw["tools_fn"] = lambda: [t for t in base_tools() if t.get("name") not in off and not (t.get("type") == "web_search" and "web_search" in off)]
        try:
            answer, items, steps = native_agent.run(
            session=task.conversation_id, model=model, effort=eff, question=question, history=self._native_history(task.conversation_id), instructions=instructions, emit=emit, find_skill=find_skill,
            checkpoint=lambda items, _cid=task.conversation_id: self._checkpoint(_cid, items),
            cancel=lambda: task.cancel_requested, cwd=work, load_skill=load_skill, on_text=llm_calls.push_draft, nudge=nudge, escalate_to=eff, allow_ask=task.allow_ask,
            mid_effort=None, project_id=project_id, permit=permit, delegate_model=delegate_model, delegate_call=delegate_call, **extra_kw,  # after a tool result the same level as the answer: reading results and writing the answer use the starting tier, not less
            delegate_effort=roles.get("subagent_effort") or "medium", max_parallel=int(roles.get("subagent_max") or 3), image_call=self._image_call(),
        )
        except chat_api.ToolsUnsupported as e:
            task.draft_as_answer = False
            task.emit({"type": "notice", "text": f"This model's API does not support function calls ({str(e)[:160]})."})
            return False
        if task.cancel_requested:
            task.emit({"type": "cancelled"})
            return True
        self._native.put(task.conversation_id, items)
        native_agent.clear_resume(task.conversation_id)  # the task finished: nothing is left to continue
        if not answer:
            answer = "No answer was received. Please try again or rephrase the question."
        seen = "\n".join([question, audit.evidence_from_events(task.events), native_agent.evidence_text(items)])  # what the model was shown; not its own queries, code or timestamps
        _write_task_qc(work, receipt_start, answer, seen)  # saved for review only; the answer text below is unchanged
        # The answer is shown as written. No verification notes are added after it: the audit functions in audit.py are kept for evaluation only.
        note = ""
        if steps == 0 and len(answer) > 60 and audit.has_identifiers(answer) and not audit.looks_like_calculation(task.prompt):
            note += audit.NO_TOOLS_NOTE  # identifiers or addresses with no search behind them; a plain explanation or calculation needs no warning
        task.emit({"type": "answer", "text": answer + note})
        task.emit({"type": "done"})
        if memory_on:  # the project's work log: what this task did, for later tasks in the project (no model call)
            try:
                worklog.record(project_id, task.conversation_id, task.id, task.prompt, answer)
            except OSError as e:
                print(f"work log not saved: {type(e).__name__}: {e}")
        if memory_on and roles.get("memory_auto", True):
            self._learn_later(task.prompt, answer, project_id, llm)
        return True

    def _roles(self) -> dict[str, Any]:
        """The Settings the loop reads (sub-agent count and effort, image model, memory switches). Missing values read as their defaults."""
        fn = getattr(self, "role_settings", None)
        try:
            return dict(fn()) if fn else {}
        except Exception:  # Settings that cannot be read fall back to the defaults, not to a failed task
            return {}

    def _image_call(self):
        """(path, question) -> the image model's answer, when Settings sets an image model; None otherwise. Paths are limited to the
        workspace and uploads, like every other file the agent opens."""
        fn = getattr(self, "image_target", None)
        try:
            target = fn() if fn else None
        except Exception:
            target = None
        if not target:
            return None
        from biomni_ui import vision

        base, key, name = target

        def call(path: str, question: str) -> str:
            real = files.resolve(path, self.roots)
            if not real:
                return "That file is not in the workspace or uploads, so it cannot be opened."
            return vision.describe(base, key, name, Path(real), question)

        return call

    def _learn_later(self, question: str, answer: str, project_id: str | None, llm: Any) -> None:
        """Suggest lasting facts from a finished answer for the user's memory, in the background. Suggestions wait for approval in
        Settings, so nothing here changes what a task uses; any failure is logged and the answer already shown is not affected."""
        if llm is None:
            return

        def run() -> None:
            try:
                from biomni_ui import assist, notes as user_notes

                user_notes.learn(question, answer, project_id, lambda system, user: assist._ask(llm, system, user))
            except Exception as e:  # memory is an extra; a failed suggestion is not an error for the user
                print(f"memory suggestions skipped: {type(e).__name__}: {e}")

        threading.Thread(target=run, name="memory-suggest", daemon=True).start()

    def _drive(self, agent, task: Task) -> None:
        """Run one task with the native loop, the only agent path. A model that cannot call tools cannot run it: the task says so."""
        agent.critic_count = 0
        agent.user_task = task.agent_prompt
        llm_calls.set_draft_sink(task.emit_draft)
        from biomni_ui import notes  # a message that is only a remember command is kept for later tasks and answered without a model call
        remembered = notes.parse(task.prompt)
        if remembered:
            notes.add(remembered)
            task.emit({"type": "answer", "text": f"Remembered: {remembered}\n\nLater tasks will take it into account; you can view or delete it in Settings."})
            task.emit({"type": "done"})
            return
        if self._native_lane(agent, task):
            return
        task.emit({"type": "error", "message": "This model does not support the function calls the agent needs, so it cannot run tasks. Pick a model that supports function calls under \"Models and connections\" (for example ChatGPT membership, or a model on an OpenAI-compatible API)."})
