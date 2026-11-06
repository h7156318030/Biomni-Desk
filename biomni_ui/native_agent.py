"""The agent loop the official app uses: one model, function calling, plain shell steps.

No difficulty rating and no text protocol: the model thinks as long as it needs (low effort thinks 1-6 s), says in one
sentence what it is about to do, then calls `bash` (curl to public APIs, python for analysis), the built-in web search, or a
literature search; each call has a human title. The loop ends when the model answers without calling anything.

It sits next to the A1 agent: `BIOMNI_UI_AGENT=a1` brings the old path back, and anything that is not the ChatGPT backend
still goes to A1.
"""

from __future__ import annotations

import functools
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable

import httpx

from biomni_ui import usage as usage_stats
from biomni_ui.effort import FLOOR as EFFORT_FLOOR

NL = chr(10)
BASH_TIMEOUT = 60  # a curl that hangs must not hold a step for two minutes
OUTPUT_HEAD, OUTPUT_TAIL = 3500, 2500
HISTORY_ITEMS = 60  # what a conversation keeps for its follow-ups

_BLOCKED = re.compile(r"\brm\s+-rf?\s+(/|~|\*|\.\.?)(\s|$)|\bmkfs\b|\bshutdown\b|\bformat\s+[a-z]:|\bdel\s+/[sq]\b|:\(\)\s*\{", re.I)

ALL_TOOLS: list[dict[str, Any]] = [
    {"type": "web_search"},
    {
        "type": "function",
        "name": "bash",
        "description": (
            "Run a bash command on the user's machine (cwd = the project folder; `python` is the project's Python with pandas, scipy, "
            "biopython, scanpy, rdkit and the project's own modules importable; `curl` reaches public APIs). Returns stdout+stderr. "
            "One command per step; save files you create in the current folder."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "A short human title of this step, in the user's language (e.g. Look up ClinVar records)."},
                "command": {"type": "string", "description": "The bash command."},
            },
            "required": ["title", "command"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "todo",
        "description": (
            "Show the user your plan as a checklist and keep it current. For a task that needs several steps (more than three tool calls), call this first with the steps, "
            "then again whenever a step is done. Send it in the same turn as the first real step, not on its own. Do not use it for a simple question."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"content": {"type": "string"}, "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]}},
                        "required": ["content", "status"],
                        "additionalProperties": False,
                    },
                    "description": "The whole list every time, in order.",
                }
            },
            "required": ["items"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "python",
        "description": (
            "Run Python in a persistent session: variables and imports stay alive between steps, so only the first step pays for importing pandas, scipy, matplotlib "
            "or the Biomni tool modules. Use it for analysis, charts and for calling Biomni's specialist functions (`from biomni.tool.database import query_uniprot`, "
            "`biomni_ui.dbtools`, `biomni_ui.lit`); `find_tools('english keywords')` lists matching functions with their import paths and parameters. "
            "cwd = the project folder; save files you create there. The value of the last expression is printed."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "A short human title of this step, in the user's language (e.g. Plot a temperature curve)."},
                "code": {"type": "string", "description": "Python code."},
            },
            "required": ["title", "code"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "use_skill",
        "description": "Load the full manual of one skill from the skill catalog (verified API recipes, analysis workflows, quality checks).",
        "parameters": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "The skill id from the catalog."}},
            "required": ["name"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "search_literature",
        "description": "Search PubMed and Europe PMC (papers and preprints). Returns title, journal, year, PMID/DOI and, when available, the abstract start.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short human title of this step."},
                "query": {"type": "string", "description": "PubMed-style English query, e.g. 'BRCA1 AND c.5266dup'."},
            },
            "required": ["title", "query"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "find_tools",
        "description": (
            "Search Biomni's specialist tool catalog (about 250 ready-made tools: database queries such as UniProt/ClinVar/ChEMBL/Open Targets/ClinicalTrials, "
            "genomics, pharmacology, immunology, literature and author papers, charts and reports). Give English keywords. Returns name, parameters and a "
            "one-line description of the best matches; call one with run_tool."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short human title of this step, in the user's language."},
                "query": {"type": "string", "description": "English keywords, e.g. 'clinical trials gene therapy' or 'protein structure'."},
            },
            "required": ["title", "query"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "run_tool",
        "description": "Run one specialist tool found with find_tools. Returns what the tool printed and returned (or why it failed). Runs inside the app, so tools that need a model work.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short human title of this step, in the user's language."},
                "name": {"type": "string", "description": "The tool name exactly as find_tools printed it."},
                "arguments": {"type": "object", "description": "Keyword arguments of the tool as a JSON object, e.g. {\"condition\": \"beta thalassemia\"}."},
            },
            "required": ["title", "name", "arguments"],
            "additionalProperties": False,
        },
    },
]

_CORE = {"bash", "python", "todo", "ask_user", "delegate_task", "propose_memory"}


def active_tools() -> list[dict[str, Any]]:
    """The model's tools, as in the official app: web search and the shell. The specialist tools are plain Python functions the shell can import
    (no picking step before the first move); BIOMNI_UI_EXTRA_TOOLS=1 adds search_literature, use_skill, find_tools and run_tool."""
    if os.environ.get("BIOMNI_UI_EXTRA_TOOLS", "0") == "1":
        return ALL_TOOLS
    keep = _CORE | {"find_tools", "run_tool"} | ({"use_skill", "find_skills"} if os.environ.get("BIOMNI_UI_SKILLS", "1") == "1" else set())  # find_tools / run_tool: the Biomni functions are found and called, not guessed  # skills: a catalog in the prompt, a manual loaded on demand
    return [t for t in ALL_TOOLS if t.get("type") == "web_search" or t.get("name") in keep]


TOOLS = ALL_TOOLS  # kept for callers that list every tool

# For models whose provider has no search tool of its own: the same two capabilities as ordinary functions (our own search and page reader).
SKILL_FIND_SPEC: dict[str, Any] = {
    "type": "function",
    "name": "find_skills",
    "description": ("Search the skill library (verified procedures for specialist analyses and database queries) by keywords. Returns the best "
                    "matches as id and title; load the full manual of one with use_skill. Use it before a specialist analysis you have not done before."),
    "parameters": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "A short human title of this step, in the user's language."},
            "query": {"type": "string", "description": "Keywords, e.g. target druggability, scRNA trajectory, GWAS fine-mapping."},
        },
        "required": ["title", "query"],
        "additionalProperties": False,
    },
}

ALL_TOOLS.append(SKILL_FIND_SPEC)  # find_skills: offered with use_skill when skills are on

ASK_USER_SPEC: dict[str, Any] = {
    "type": "function",
    "name": "ask_user",
    "description": ("Ask the user to choose before you go on, when the answer depends on a choice only the user can make (which of several different entities, "
                    "which time range or sample, which of two plans) and searching cannot settle it. The turn ends here; the user's pick comes back as their next "
                    "message. Use it only for a choice that changes the answer, at most once per task; otherwise decide and state the assumption."),
    "parameters": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "A short human title of this step, in the user's language."},
            "question": {"type": "string", "description": "The question, in the user's language, with what each option means."},
            "options": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 4, "description": "2 to 4 short options the user can click."},
        },
        "required": ["title", "question", "options"],
        "additionalProperties": False,
    },
}
ALL_TOOLS.append(ASK_USER_SPEC)

SUB_STEPS = 12  # a sub-agent takes at most this many tool steps, then must answer from what it has
DELEGATE_SPEC: dict[str, Any] = {
    "type": "function",
    "name": "delegate_task",
    "description": ("Start one self-contained sub-task on a sub-agent. It runs in the background, in parallel with you (several can run at once), "
                    f"with its own tools (web search, databases, Python; up to {SUB_STEPS} steps), and its short result with sources arrives as a message "
                    "when it finishes. Its working steps stay out of this conversation. It cannot ask you questions, so put everything it needs in "
                    "`task`: what to find or compute, which sources, and the exact form of the result. Hand off each piece that takes several steps and "
                    "does not depend on your other steps, so that the work runs side by side; keep the quick steps for yourself."),
    "parameters": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "A short human title of this step, in the user's language."},
            "task": {"type": "string", "description": "The sub-task, fully specified: what to find or compute, and what the result must contain."},
            "context": {"type": "string", "description": "Anything the sub-agent needs that is not in the task (identifiers, earlier results). Optional."},
        },
        "required": ["title", "task"],
        "additionalProperties": False,
    },
}
ALL_TOOLS.append(DELEGATE_SPEC)

WAIT_SPEC: dict[str, Any] = {
    "type": "function",
    "name": "wait_subagents",
    "description": ("Wait for the sub-agents you started with delegate_task and get their results now. Leave `ids` out to wait for all of them. "
                    "Use it only when your next step needs a result. Otherwise keep working: a result that finishes meanwhile arrives as a message."),
    "parameters": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "A short human title of this step, in the user's language."},
            "ids": {"type": "array", "items": {"type": "string"}, "description": "The sub-agent ids returned when they were started (for example sub-1). Optional."},
        },
        "required": ["title"],
        "additionalProperties": False,
    },
}

PROPOSE_MEMORY_SPEC: dict[str, Any] = {
    "type": "function",
    "name": "propose_memory",
    "description": ("Suggest one fact or standing preference for the user's memory, for example a species, a unit convention or a standing rule "
                    "the user has stated. It is not used until the user approves it in Settings. Use it rarely: only for something the user said "
                    "that should hold in later tasks. Never propose personal data, credentials or anything you only guessed."),
    "parameters": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "A short human title of this step, in the user's language."},
            "text": {"type": "string", "description": "The note, one short sentence, in the user's language (at most 300 characters)."},
        },
        "required": ["title", "text"],
        "additionalProperties": False,
    },
}
ALL_TOOLS.append(PROPOSE_MEMORY_SPEC)


FORWARDED = ("code", "observation", "tool", "reasoning")  # what a sub-agent shows in the session, under its own card


LOOK_SPEC: dict[str, Any] = {
    "type": "function",
    "name": "look_at_image",
    "description": ("Look at one picture file (png, jpg, gif or webp) and answer a question about it. An image model reads the picture and "
                    "returns its text answer; the picture itself is not shown to you. Use it for any picture the user uploaded and for any "
                    "figure you produced that you need to check. Give the file path as it appears in the file locations."),
    "parameters": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "A short human title of this step, in the user's language."},
            "path": {"type": "string", "description": "The picture's file path."},
            "question": {"type": "string", "description": "What to find out or describe in the picture."},
        },
        "required": ["title", "path"],
        "additionalProperties": False,
    },
}


def _delegate(task: str, context: str, *, model: str, effort: str, instructions: str, cancel: Callable[[], bool], cwd: Path,
              load_skill: Callable[[str], str] | None, find_skill: Callable[[str], str] | None, call: Callable[..., Any],
              permit: Callable[[str, str], str] | None = None, emit: Callable[[dict[str, Any]], None] | None = None) -> str:
    """Run one sub-task as a separate pass of the same loop: its own history, its own step cap, no questions to the user, and no
    sub-agents of its own. The session shows it as a card: a "subagent" event when it starts and when it ends, and its steps
    tagged with its id. Only its final answer goes back to the main agent."""
    from biomni_ui import pykernel

    sid = f"sub-{time.time_ns()}"
    question = f"Sub-task from the main agent:\n{task.strip()}"
    if context.strip():
        question += f"\n\nContext from the main agent:\n{context.strip()}"
    question += "\n\nGive the result the task asks for, and name the sources or tool outputs it rests on. Keep it short."

    def forward(event: dict[str, Any]) -> None:
        if emit is not None and event.get("type") in FORWARDED:
            emit({**event, "sub": sid})

    if emit is not None:
        emit({"type": "subagent", "id": sid, "status": "running", "task": task.strip()[:400], "steps": 0})
    try:
        answer, _items, steps = _run_loop(sess=sid, model=model, effort=effort, question=question, history=[], instructions=instructions,
                                          emit=forward, cancel=cancel, cwd=cwd, load_skill=load_skill, find_skill=find_skill, call=call,
                                          tools_fn=lambda: [t for t in active_tools() if t.get("name") != "delegate_task"], allow_ask=False,
                                          max_steps=SUB_STEPS, permit=permit, allow_subagents=False)
    except Exception as e:  # reported to the main agent and shown on the card; the main task goes on
        if emit is not None:
            emit({"type": "subagent", "id": sid, "status": "failed", "steps": 0, "answer": f"{type(e).__name__}: {str(e)[:200]}"})
        return f"[sub-agent failed: {type(e).__name__}]"
    finally:
        pykernel.POOL.close(sid)
    if emit is not None:
        emit({"type": "subagent", "id": sid, "status": "done", "steps": steps, "answer": (answer or "").strip()[:1500]})
    return f"[sub-agent finished in {steps} steps]\n{(answer or '').strip() or 'The sub-agent gave no answer.'}"[:6000]

SEARCH_FUNCS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "web_search",
        "description": (
            "Search the web (360 and Bing). Returns numbered results with title, site, link and a snippet. A snippet is not the page: read the best links with read_webpage "
            "before relying on a number, a date or a method detail. Chinese or English; for a rare name use the name itself, plus one word that tells it apart."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "A short human title of this step, in the user's language."},
                "query": {"type": "string", "description": "Search words (one search)."},
                "queries": {"type": "array", "items": {"type": "string"}, "description": "Several searches at once (they run side by side): put every keyword set you need in this one call."},
            },
            "required": ["title"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "read_webpage",
        "description": "Download a web page and return its title and main text (menus and scripts removed). Use it on the links a search returned.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "A short human title of this step, in the user's language."},
                "url": {"type": "string", "description": "The page address (one page)."},
                "urls": {"type": "array", "items": {"type": "string"}, "description": "Several pages at once (they are fetched side by side): put every link you want to read in this one call."},
            },
            "required": ["title"],
            "additionalProperties": False,
        },
    },
]


def chat_tools_list(question: str | None = None) -> list[dict[str, Any]]:
    """The tools for a model on a chat-completions endpoint: everything except the ChatGPT-only search, plus our own search functions and the
    direct database calls that the question calls for (all of them when no question is given)."""
    direct = direct_specs(question) if os.environ.get("BIOMNI_UI_DIRECT_TOOLS", "1") != "0" else []
    return [t for t in active_tools() if t.get("type") != "web_search"] + SEARCH_FUNCS + direct


SYSTEM = """You are Biomni, a biomedical research assistant working on the user's computer. Reply in the same language as the user's question: English for English questions, Chinese for Chinese questions.

When a question arrives, first decide how to proceed. Base the decision on the cost of a wrong answer and on whether the methods are disputed, not on the length of the question, and not on the assumption that every biomedical question needs a web search:

1. Do it directly, with no web search and no plan, when the task does not depend on external facts. This covers conversions and calculations (dilutions, doses, statistics), translation, rewriting, writing, code and formulas, and analysis of data or material the user has already given you.
2. Look it up first, then answer, for external facts (people, companies, drugs, clinical trials, papers, variants, gene locations, database records, news, weather, regulations, numbers and dates). Use search to verify. If the user only wants your existing knowledge (for example "explain the principle"), you may answer directly.
3. Plan first, then work, for tasks where the method involves choices, thresholds must be set, the choice affects the biological interpretation, several steps are needed (more than three tool calls), or a report or slide deck is requested. List the steps with `todo`, state the key methodological choices, and update the list after each step. Ask the user before any irreversible action.
4. Ambiguous reference (which person, file or environment): first spend one or two cheap lookups (the conversation context, files, web search). If you find it, continue on that basis and state your understanding. If one name refers to two or more different entities that each have real stakes (companies, institutions, genes, drugs), do not pick one and answer. Use `ask_user` to list them, describing what each one is, and let the user choose. If nothing is found: when the choice would change the conclusion, use `ask_user` with 2 to 4 options; otherwise continue with the most plausible reading, state the assumption, and let the user correct it.

Execution
- Prefer ready-made, trustworthy sources (official databases, NCBI, UniProt, ChEMBL, company websites). Do not reconstruct APIs from memory: when an API format is unfamiliar, check the official documentation before writing the call. When something fails, first decide what kind of failure it is. A parameter or syntax error: correct it and retry, trying a few variants before concluding. A service that is down: switch to another source, or say so. Ask the user only about their preferences or costs (budget, whether to continue). Decide purely technical fixes yourself.
- Tools: `web_search` (to learn what something is and its current status; `queries` is an array that runs several keyword searches in parallel). `python`: one persistent Python session (variables and imports persist between steps; only the first call waits for libraries to load); use it for analysis, plots and calling specialist functions. `bash`: command line, curl, file management. `todo`: a plan checklist. `delegate_task`: start one self-contained sub-task (for example, check one database for a list of genes, or read and summarise one long paper) on a sub-agent with its own steps. It runs in the background, in parallel with you, and its short result arrives as a message when it finishes; its working steps stay out of this conversation. Plan so that independent parts run side by side: as soon as you see parts that do not depend on each other, start each one as a sub-agent in the same round, give each everything it needs in `task` (what to find, which sources, the exact form of the result), and keep working on the parts you do yourself. Call `wait_subagents` only when your next step needs a result. Do not hand off a quick step you must see yourself. This applies in every round, not only the first. When several steps do not depend on each other, issue them together in the same round instead of one at a time: for several keywords use the `queries` array of web_search; for several pages use the `urls` array of read_webpage; for several independent commands or database queries, issue all the calls in the same round (the system runs them at the same time, which is much faster). Split into rounds only when a later step needs an earlier step's result. Before each round, ask which remaining steps do not depend on this step's result, and issue those now rather than leaving them for the next round.
- Skills: before a specialist analysis, or before querying a type of database, search the skill manuals by keyword with `find_skills` (for example "target druggability" or "scRNA trajectory"). When a suitable one turns up, load its full text by id with `use_skill`. If none fits, use a function or web search directly.
- Biomni's specialist functions are imported and called directly in `python` (modules are grouped by field under `biomni.tool`). The task instructions list the functions relevant to the question, with import paths and required parameters, and the relevant skills. Call the listed ones directly: import first, assign the result and print it. Do not guess function names from memory. For any other function, search with `find_tools('English keywords')`. `biomni_ui.dbtools` and `biomni_ui.lit` are fast database and literature functions.
- {STYLE}
- Add `-m 20` (a 20-second timeout) to every curl call. If an endpoint hangs or returns a 5xx error, switch the method or the source; do not wait.
- Web search results are mostly summaries. When you need specific numbers, dates or method details, read the source page itself (use `read_webpage` if available, otherwise requests in python). Do not write numbers from a summary alone.
- When the user gives only a name (a company, gene, drug or person, for example "look up X" or "what is X"), do not ask "do you mean ...?". Go straight to the most common reading and give a substantive overview: identity and role, main products or pipeline, clinical trials (if any), representative papers or authoritative sources, each with a source. Begin by stating what you took the subject to be. If the name is ambiguous, list the candidates and say which one you chose. A name usually needs two to four search steps. Do not fetch every subpage in the name of completeness, and do not delete or reorganise files for tidiness.
- Computation and analysis: validate the pipeline on a small sample first, then scale up. Split any task expected to take more than 30 minutes into blocks of one to two hours each, save each block's intermediate state under checkpoints/ in the current directory, and write a manifest (file names, counts, sizes). When resuming, check the manifest first. If it does not verify, treat the checkpoint as absent and redo that block.
- Earlier parts of this conversation are already in your context. When you need the full record (for example "that earlier result"), read execution_trace/transcript.jsonl and trace.ipynb in the current directory (with grep or python). Do not rely on memory.
- To show an image, the image must already be a file in the current directory. Download web images with `curl -L -m 30 -o FILENAME`, then confirm with `file FILENAME` that it is really an image and not a web page. Draw data charts with matplotlib in python and save them as png (Chinese labels work directly). Reference images in the answer as `![caption](FILENAME)`; the page displays them. Do not paste image URLs you have not downloaded and verified. For dynamic images or images that cannot be embedded, redraw the chart from the data you found instead of giving only a link.
- In every round that makes tool calls, say before the calls, in one or two sentences, what this round does and what the previous step produced. Name the specific numbers, files, datasets or parameters, for example "the lentiviral route document is ready; now querying two comparison databases at once". Simple single-step lookups, conversions and direct answers need no narration. Do not post uninformative lines such as "running the analysis". Do not write process narration in the answer body such as "first I'll search" or "now I'll check"; the process is shown in the steps automatically. Do not ask "shall I search?" first, and do not apologise first.

Pace (deliver once it is sufficient)
- Before you start, decide what to deliver (one fact, a short profile, one sequence plus one figure), and stop once you have enough. When a question has several parts, each part needs a source; do not rely on the first source alone. Do not retry for a prettier layout.
- If a route is blocked (login required, 404, refused), switch to another route. Do not try the same site more than three times. If you truly cannot get something, write "not retrieved" and where it got stuck, and let the user decide.
- Figures: draw it once; if it looks right at a glance, deliver it. Allow at most one more change to fonts and spacing. Do not redraw repeatedly.
- Do as much as possible in every round, not only the first: issue independent calls together, and write a related series of commands as one script that runs once. Do not do one small thing per round.

Verification (before you deliver)
- Files: after generating or downloading, spot-check them (file header, line count, size, whether they open). Report success only once the file is complete.
- Data: do not fabricate, simulate or invent data. Every finding comes from data the user gave you, or from sources you actually retrieved in this round. Put a source after every external fact (a link, PMID, DOI or registry number). Every table row needs a source column or source link. Sources must be ones you really retrieved; do not invent identifiers or URLs. To cite a web page, write [@N]: each page in search and page-read results carries a number [@N]; write [@N] in the answer and the system replaces it with that page's link. Cite only pages that carry a number (for a search result that gives only a summary, open the page with read_webpage first). Cite papers by PMID and DOI; registry numbers as they are. Do not use shorthand such as "news/89" or "item 3 on the official site", and do not cite pages you have not opened. Data fetched through an API (REST, JSON) is sourced to the address you queried, or to an entry page you confirmed opens with `curl -I` or read_webpage. Do not reconstruct URLs from memory.
- If you cannot find something, say what you searched for and what you did not find. Do not present a lack of evidence as proof of absence.
- Keep names of people, institutions and companies as they are written in the source. If the source is in English, use the English name. Do not transliterate or translate names yourself: an invented company name is a serious error.
- When the question asks you to "list", "find" or "which are there", list every matching result from the sources, one by one, each with its source. For results that do not qualify, give the reason for exclusion. Do not pick one and stop.

Delivery
- Answers to biology questions must explain the biological meaning (function, mechanism, structure or pathway, clinical or experimental implications), not just list numbers. State which function, database or paper each datum comes from.
- For values in tables (ranges, positions, concentrations, doses), prefer the values returned by structured databases (such as InterPro, UniProt, Open Targets, gnomAD). Where the literature gives different values, state the source and the difference in the notes, and do not replace the tool's value.
- Before citing a web page, read its full text with read_webpage. If you saw only the search summary, say in the answer that it is a summary and not a page you read.
- Open the answer with the conclusion in no more than three sentences. Organise the rest by task type: for facts and literature, key points each with a source, and tables where useful; for analysis, data, methods, results and caveats; for plans, the recommended plan, the basis and the risks. If you searched the web, give the query date at the end. Do not paste long code into the answer.
- Save result files in the current directory, and say what each file is and how to use it.
- Use the findings you retrieved in the answer. Every aspect of the question should have matching content. Key numbers, dates and disagreements between sources go into the body. Important directions you checked but did not put in the body get one sentence at the end saying why they were left out (for example: the source was a video, it could not be verified, or it is unrelated).
- If the user's view is wrong, say so directly, without flattery. Use the simplest method that guarantees accuracy. If you cannot do something, say so.
"""


STYLES = {
    "biomni": "Data and analysis: first search for ready-made Biomni functions in python with `find_tools('English keywords')` (it lists function names, import paths and parameters) and call the suitable ones directly. Only when none fits, or a function fails, call public APIs directly with curl -s (one request at a time; inspect results with | head -c 3000 or | python -m json.tool). Write python for parsing, calculations and plots.",
    "curl": "Data: call public APIs directly with curl -s, one request at a time as in a terminal; inspect results with | head -c 3000 or | python -m json.tool (this machine has python only, not python3). Write python only when you need parsing, calculations or plots.",
    "python": "Data and analysis: use python for everything (requests, pandas, scipy and so on), written in a bash heredoc.",
}


def system_prompt(style: str = "curl", catalog: str = "") -> str:
    text = SYSTEM.replace("{STYLE}", STYLES.get(style, STYLES["curl"]))
    if catalog:
        text += "\n\nSkill catalogue (each line is a name and its scope. Load the full manual with use_skill by id only when the task matches exactly and you cannot write a given API call or procedure; if it does not match, do not load it):\n" + catalog
    return text


# ---------------------------------------------------------------------------------------------- tools

def bash_path() -> str | None:
    for p in (r"C:\Program Files\Git\bin\bash.exe", r"C:\Program Files (x86)\Git\bin\bash.exe"):
        if Path(p).exists():
            return p
    found = shutil.which("bash")
    return found if found and "system32" not in found.lower() else None


def run_bash(command: str, cwd: Path, cancel: Callable[[], bool] = lambda: False, timeout: int = BASH_TIMEOUT) -> str:
    if _BLOCKED.search(command):
        return "Refused: this command would mass-delete or damage the system. Please use another approach."
    exe = bash_path()
    if exe is None:
        return "bash was not found on this computer (Git for Windows needs to be installed)."
    scripts = Path(sys.prefix) / "Scripts"  # the virtualenv's own `python`, not whatever the base interpreter's folder holds
    path = os.pathsep.join(str(d) for d in (scripts, Path(sys.executable).parent) if d.is_dir()) + os.pathsep + os.environ.get("PATH", "")
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1", "PATH": path, "NO_PROXY": "localhost,127.0.0.1,::1", "MATPLOTLIBRC": str(Path(__file__).parent / "mpl"), "MPLBACKEND": "Agg"}
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        proc = subprocess.Popen([exe, "-c", command], cwd=str(cwd), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", creationflags=flags)
    except OSError as e:
        return f"Could not start the command: {e}"
    t0 = time.time()
    out: list[str] = []
    reader = threading.Thread(target=lambda: out.append(proc.stdout.read() if proc.stdout else ""), daemon=True)
    reader.start()
    while reader.is_alive():
        reader.join(0.3)
        if cancel():
            proc.kill()
            return "(cancelled)"
        if time.time() - t0 > timeout:
            proc.kill()
            reader.join(1)
            return truncate("".join(out)) + f"\n(exceeded {timeout} seconds; stopped)"
    proc.wait()
    text = "".join(out)
    if proc.returncode not in (0, None):
        text = text.rstrip() + f"\n(exit code {proc.returncode})"
    return truncate(text) or "(no output)"


def truncate(text: str) -> str:
    if len(text) <= OUTPUT_HEAD + OUTPUT_TAIL:
        return text
    return text[:OUTPUT_HEAD] + f"\n…(middle {len(text) - OUTPUT_HEAD - OUTPUT_TAIL} characters omitted)…\n" + text[-OUTPUT_TAIL:]


def run_literature(query: str) -> str:
    from biomni_ui import lit

    parts = []
    for name, fn in (("PubMed", lit.pubmed_search), ("Europe PMC", lit.europepmc_search)):
        try:
            parts.append(f"## {name}\n{fn(query)}")
        except Exception as e:
            parts.append(f"## {name}\nSearch failed: {type(e).__name__}: {str(e)[:120]}")
    return truncate("\n\n".join(parts))


# ---------------------------------------------------------------------------------------------- model

def _headers() -> dict[str, str]:
    from biomni_ui import chatgpt_api as c

    token = c.fresh_access_token(c.AUTH_FILE)
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "text/event-stream", "User-Agent": c.USER_AGENT, "originator": "biomni-lite", **c.account_headers(token)}


class ModelStalled(RuntimeError):
    """The model went quiet or ran past the time a single call may take."""


READ_LIMIT = 150  # seconds without any data from the model before the call is cut


def call_model(model: str, effort: str, instructions: str, items: list[dict[str, Any]], tools: list[dict[str, Any]], on_text: Callable[[str], None] | None = None, timeout: int = 420) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """One streamed model call. Returns (output items, {"seconds", "usage"})."""
    from biomni_ui import chatgpt_api as c

    body = {
        "model": model, "instructions": instructions, "input": items, "tools": tools, "tool_choice": "auto" if tools else "none",
        "parallel_tool_calls": True, "store": False, "stream": True, "reasoning": {"effort": effort},
        "include": ["reasoning.encrypted_content", "web_search_call.action.sources"],
    }
    t0 = time.time()
    for attempt in range(3):
        out: list[dict[str, Any]] = []
        usage: dict[str, Any] = {}
        text: list[str] = []
        try:
            with httpx.Client(timeout=httpx.Timeout(READ_LIMIT, connect=30)) as client:
                with client.stream("POST", f"{c.BASE_URL}/responses", json=body, headers=_headers()) as resp:
                    if resp.status_code != 200:
                        resp.read()
                        raise RuntimeError(c.explain_http_error(resp.status_code, resp.text))
                    for ev in c.iter_sse(resp.iter_lines()):
                        if time.time() - t0 > timeout:
                            raise ModelStalled(f"The model had not finished this step after {timeout} seconds")
                        kind = ev.get("type", "")
                        if kind == "response.output_text.delta":
                            text.append(ev.get("delta", ""))
                            if on_text:
                                on_text("".join(text))
                        elif kind == "response.output_item.done":
                            out.append(ev.get("item") or {})
                        elif kind == "response.completed":
                            usage = (ev.get("response") or {}).get("usage") or {}
                        elif kind in ("response.failed", "error"):
                            err = (ev.get("response") or {}).get("error") or ev.get("error") or ev
                            raise RuntimeError(f"ChatGPT returned an error: {str(err.get('message', err))[:300]}")
            return out, {"seconds": round(time.time() - t0, 1), "usage": usage}
        except (httpx.ConnectError, httpx.RemoteProtocolError, httpx.ConnectTimeout, httpx.ReadTimeout, ModelStalled):
            if attempt == 2:
                raise
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("unreachable")


def message_text(item: dict[str, Any]) -> str:
    return "".join(p.get("text", "") for p in item.get("content", []) if p.get("type") == "output_text").strip()


_SNAP_SKIP = {".venv", "node_modules", ".next", "__pycache__", ".git", "ui_data", "data", "workspace", "biomni", "biomni_ui", "web", "builds", "vendor", "tmp", "scripts", "biomni_lite.egg-info"}


def snapshot(cwd: Path) -> dict[str, tuple[int, int]]:
    """{path: (mtime_ns, size)} of the result-type files in the working folder and one level of sub-folders (cheap: a few hundred entries)."""
    from biomni_ui import files as ui_files

    out: dict[str, tuple[int, int]] = {}

    def scan(folder: Path, depth: int) -> None:
        try:
            with os.scandir(folder) as it:
                for e in it:
                    if e.is_file(follow_symlinks=False):
                        if Path(e.name).suffix.lower() in ui_files.ALLOWED_EXT:
                            st = e.stat()
                            out[str(Path(e.path))] = (st.st_mtime_ns, st.st_size)
                    elif depth < 1 and e.is_dir(follow_symlinks=False) and e.name not in _SNAP_SKIP and not e.name.startswith("."):
                        scan(Path(e.path), depth + 1)
        except OSError:
            pass

    scan(Path(cwd), 0)
    return out


def changed_files(before: dict[str, tuple[int, int]], after: dict[str, tuple[int, int]]) -> list[str]:
    """Files a step created or rewrote, newest first."""
    paths = [p for p, v in after.items() if before.get(p) != v]
    return sorted(paths, key=lambda p: -after[p][0])


def todo_steps(items: Any) -> list[dict[str, str]]:
    """The model's to-do list as the page's plan: [{content, status: pending|in_progress|completed}] -> [{text, status: todo|done}]."""
    out = []
    for it in items if isinstance(items, list) else []:
        if isinstance(it, dict) and str(it.get("content") or "").strip():
            out.append({"text": str(it["content"]).strip()[:200], "status": "done" if it.get("status") == "completed" else "todo"})
    return out[:12]


def _receipt(cwd: Path, fc: dict[str, Any], arguments: Any, result: str, t0: float, files: list[str] | None = None) -> dict[str, Any] | None:
    """The receipt for one tool call (see receipts.py). Never raises: a receipt that cannot be written must not stop the task."""
    from biomni_ui import receipts

    try:
        return receipts.record(cwd, fc.get("call_id"), str(fc.get("name")), arguments, result, time.time() - t0, files)
    except Exception:
        return None


def evidence_text(items: list[dict[str, Any]], question: str = "") -> str:
    """What the model was shown or fetched: the question, what its commands and searches returned, and the user's own messages.

    The commands and search queries the model wrote are not evidence: a figure it typed into a query (a domain boundary it remembered, say)
    would otherwise count as a source for itself."""
    parts = [question]
    for it in items:
        kind = it.get("type")
        if kind == "function_call_output":
            parts.append(str(it.get("output") or ""))
        elif kind == "message" and it.get("role") == "user":
            parts.append(_text_of(it))
    return chr(10).join(parts)


def evidence_complete(items: list[dict[str, Any]]) -> bool:
    """True when everything the model read is in `items` as text. A provider-side search (the ChatGPT backend's own) returns page text only to the model,
    so a claim from it cannot be looked up here and the fact check stays off."""
    return not any(it.get("type") == "web_search_call" for it in items)


def _text_of(item: dict[str, Any]) -> str:
    return "".join(str(p.get("text", "")) for p in item.get("content") or [] if isinstance(p, dict))


JUDGE_SYSTEM = """You are a fast "is it enough?" judge. You do one thing: decide whether the material the assistant has already retrieved is enough to answer the user's question at the depth the user asked for.
- First look at what the user asks and how deep it must go: a name, one fact, a short profile, a complete list, one analysis, or a deliverable such as a file, figure or table.
- Then check whether the material covers the key content that depth needs, and whether every deliverable the user explicitly asked for has been produced.
- If it is enough, answer ENOUGH. If key content is still missing, answer CONTINUE and say in one sentence what is missing.
- If a deliverable the user explicitly asked for (a file, figure, sequence, table or data) has not been produced or retrieved yet, and the work is not stuck (the same obstacle has not failed repeatedly), always answer CONTINUE. That is the task itself, not an extra.
- Do not answer CONTINUE merely because the answer "could be more complete". If what is missing is only supplementary material the user did not explicitly ask for, more sources, or more background, or something that can be described as "can be explored further", answer ENOUGH.
- For a name lookup (a company, gene, drug or person), a single profile paragraph is not enough. To answer ENOUGH you also need the main products or pipeline, clinical trials or regulatory progress (if any), and recent important news, each with a source. Otherwise answer CONTINUE.
- If the content, file or figure the user asked for is already there and sourced, and what remains is only swapping in better sources, repeating verification, adjusting fonts and layout, or cross-checking again, answer ENOUGH. The answer should note these and let the user decide whether to continue.
- If the same obstacle (login, 404, blocked) has been tried more than three times and the work is still going round in circles, answer ENOUGH and say where it got stuck.
The first word of your output must be ENOUGH or CONTINUE. You may follow it with one sentence of reason.
"""


def work_digest(items: list[dict[str, Any]], limit: int = 2600) -> str:
    """What has been done and found so far, one short line per step (for the judge)."""
    outputs = {str(it.get("call_id")): str(it.get("output") or "") for it in items if it.get("type") == "function_call_output"}
    lines: list[str] = []
    for it in items:
        kind = it.get("type")
        if kind == "web_search_call":
            q = (it.get("action") or {}).get("queries") or [(it.get("action") or {}).get("query", "")]
            lines.append("Web search: " + " / ".join(str(x) for x in q if x)[:100])
        elif kind == "function_call":
            try:
                args = json.loads(it.get("arguments") or "{}")
            except ValueError:
                args = {}
            what = str(args.get("title") or args.get("query") or args.get("command") or args.get("code") or args.get("url") or it.get("name"))[:80]
            got = " ".join(outputs.get(str(it.get("call_id")), "").split())[:220]
            lines.append(f"{it.get('name')}: {what}" + (f" -> {got}" if got else ""))
    text = NL.join(f"{i + 1}. {l}" for i, l in enumerate(lines))
    return text if len(text) <= limit else text[: limit // 3] + NL + "..." + NL + text[-(2 * limit // 3):]


def judge_enough(call: Callable[..., Any], model: str, effort: str, question: str, items: list[dict[str, Any]]) -> tuple[bool, str]:
    """(enough, reason): a short, tool-free call that reads the question and the digest of the work so far and says whether to stop gathering."""
    prompt = f"The user's question: {question[:600]}{NL}{NL}What has been done and found so far:{NL}{work_digest(items)}"
    try:
        out, _ = call(model, effort, JUDGE_SYSTEM, [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": prompt}]}], [], None)
    except Exception:
        return False, ""  # the judge is only an aid: when it fails the loop goes on as before
    text = NL.join(t for t in (message_text(i) for i in out if i.get("type") == "message") if t).strip()
    head = text.split(None, 1)[0].upper().strip("：:，,。.") if text else ""
    reason = re.sub(r"^\s*(ENOUGH|CONTINUE)\s*[:：,，。.、-]?\s*", "", text, flags=re.I)
    return head.startswith("ENOUGH"), reason[:160]


_FN_RE: "re.Pattern[str] | None" = None
_FN_DOC: dict[str, str] = {}


def biomni_functions_in(code: str) -> dict[str, str]:
    """{name: one-line description} of the Biomni specialist functions a piece of code mentions (for the "tools used" and "knowledge consulted" panels)."""
    global _FN_RE
    try:
        if _FN_RE is None:
            from biomni_ui import biomni_tools

            for t in biomni_tools.catalog():
                _FN_DOC.setdefault(t["name"], t["description"])
            names = sorted(_FN_DOC, key=len, reverse=True)
            _FN_RE = re.compile(r"\b(?:" + "|".join(re.escape(n) for n in names) + r")\b") if names else re.compile(r"(?!x)x")
        return {n: _FN_DOC[n] for n in dict.fromkeys(_FN_RE.findall(code or ""))}
    except Exception:
        return {}


# ---------------------------------------------------------------------------------------------- the loop

HEAVY_OUTPUT = 1200  # a tool result longer than this is cut once it is no longer one of the latest few (what the model sees)
RECENT_OUTPUTS = 6  # the latest tool results are always given in full
STORED_OUTPUT = 1500  # what a conversation keeps of one tool result


def _cut(text: str, keep: int, what: str) -> str:
    return text[:keep] + f"\n…({what} omitted, {len(text) - keep} characters)…"


def shrink_view(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """What the model sees on one call: this turn in full (its reasoning included), earlier turns without their encrypted reasoning, the latest
    tool results in full and older ones cut short. Long conversations stay fast; the stored history is not changed."""
    last_user = max((i for i, it in enumerate(items) if it.get("type") == "message" and it.get("role") == "user"), default=0)
    outs = [i for i, it in enumerate(items) if it.get("type") == "function_call_output"]
    recent = set(outs[-RECENT_OUTPUTS:])
    view: list[dict[str, Any]] = []
    for i, it in enumerate(items):
        if it.get("type") == "reasoning" and i < last_user:
            continue
        if it.get("type") == "function_call_output" and i not in recent and len(str(it.get("output") or "")) > HEAVY_OUTPUT:
            it = {**it, "output": _cut(str(it.get("output")), 800, "earlier results")}
        view.append(it)
    return view


class Conversations:
    """What each conversation said so far (kept in this process; a conversation always returns to the process that holds it)."""

    def __init__(self) -> None:
        self._items: dict[str, list[dict[str, Any]]] = {}

    def get(self, conversation_id: str) -> list[dict[str, Any]]:
        return list(self._items.get(conversation_id, []))

    def put(self, conversation_id: str, items: list[dict[str, Any]]) -> None:
        items = [({**it, "output": _cut(str(it.get("output")), 1000, "")} if it.get("type") == "function_call_output" and len(str(it.get("output") or "")) > STORED_OUTPUT else it) for it in items]
        kept = items[-HISTORY_ITEMS:] if len(items) > HISTORY_ITEMS else items
        if len(kept) < len(items):  # trimmed: start at a user message, not in the middle of a tool exchange
            start = next((i for i, it in enumerate(kept) if it.get("type") == "message" and it.get("role") == "user"), None)
            kept = kept[start:] if start is not None else []
        self._items[conversation_id] = kept


RESUME_DIR = Path(__file__).resolve().parent.parent / "ui_data" / "resume"  # the work of a task that was cut short, kept so that "continue" can pick it up


def resume_path(conversation_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_-]", "", str(conversation_id))[:80] or "conversation"
    return RESUME_DIR / f"{safe}.json"


def complete_exchange(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The items with every tool call that has its result (a call cut off before its result is dropped: the model could not resume it)."""
    answered = {str(i.get("call_id")) for i in items if i.get("type") == "function_call_output"}
    return [i for i in items if i.get("type") != "function_call" or str(i.get("call_id")) in answered]


def save_resume(conversation_id: str, items: list[dict[str, Any]]) -> None:
    path = resume_path(conversation_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"items": items}, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def load_resume(conversation_id: str) -> list[dict[str, Any]]:
    try:
        data = json.loads(resume_path(conversation_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return complete_exchange([i for i in data.get("items", []) if isinstance(i, dict)])


def clear_resume(conversation_id: str) -> None:
    try:
        resume_path(conversation_id).unlink()
    except OSError:
        pass


_PREAMBLE = re.compile(r"^\s*((?:我先|我再|我会|我来|我将|我去|我这就|让我|先)[^。\n]{2,200}。|我(?:查|搜|找|看|核对|检索|确认|读|读取|下载|画|整理)(?:一下|一查)[^。\n]{0,200}。|(?:First(?:ly)?,? I(?:'ll| will)|Let me|Now I(?:'ll| will)|I(?:'ll| will) (?:now )?(?:search|check|verify|read|download|plot|look|fetch|confirm))[^.\n]{2,200}\.)\s*", re.I)


def split_preamble(text: str) -> tuple[str, str]:
    """("我先核对…。", the rest): the model's one-sentence announcement before it searches belongs to the steps, not to the answer."""
    m = _PREAMBLE.match(text or "")
    if not m:
        return "", text
    rest = text[m.end():]
    return (m.group(1), rest) if len(rest.strip()) >= 20 else ("", text)


def strip_preamble(text: str) -> str:
    return split_preamble(text)[1]


def split_preambles(text: str, limit: int = 3) -> tuple[str, str]:
    """All the leading announcements (up to `limit` sentences) and the rest: narration of the work is a step, the answer starts at the result."""
    said: list[str] = []
    for _ in range(limit):
        pre, text = split_preamble(text)
        if not pre:
            break
        said.append(pre)
    return " ".join(said), text


_CITE_MARK = re.compile(".*?", re.S)  # the search tool's private citation markers
_MD_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)[^)]*\)")


def clean_answer(text: str, cwd: Path | None = None) -> str:
    """Take out what the page cannot show: the search tool's citation markers, and Markdown pictures that point at nothing
    (the model sometimes writes ![forecast](turn0forecast0), a handle of the search tool's own widget, or a file it never made)."""
    text = _CITE_MARK.sub("", text)
    text = re.sub(r"\[@(?!\d)([^\]\n]{1,120})\]", lambda m: "(" + m.group(1).strip() + ")", text)  # [@数据库查询] is a note, not a citation number: keep the words, drop the marker
    text = re.sub(r"\]\(sandbox:/*([^)\s]+)\)", lambda m: "](" + m.group(1) + ")", text)  # the provider's sandbox links name a file on this machine; the page serves those
    text = re.sub(r"\?utm_source=openai&", "?", text)
    text = re.sub(r"[?&]utm_source=openai(?=[&)\s\]#]|$)", "", text)  # the search tool's tracking tail: the same page, and it must match the address the search returned

    base = Path(cwd or Path.cwd())

    def where(src: str) -> Path:
        return Path(src.replace("/", os.sep)) if re.match(r"^[A-Za-z]:", src) else base / src

    def shown(path: Path) -> str:
        p = path.resolve().as_posix()
        return f"<{p}>" if " " in p else p  # a path with a space needs the angle-bracket form in a Markdown link

    def keep(m: re.Match) -> str:
        src = m.group(2)
        if re.match(r"(?i)^(?:https?:|data:image/)", src):
            return m.group(0)
        path = where(src)
        return f"![{m.group(1)}]({shown(path)})" if path.is_file() else ""

    def link(m: re.Match) -> str:
        from biomni_ui import files as ui_files

        src = m.group(2)
        if re.match(r"(?i)^(?:[a-z][a-z0-9+.-]*:(?!/*[A-Za-z]:)|#|/)", src) and not re.match(r"^[A-Za-z]:", src):
            return m.group(0)  # a web address, an anchor, mailto ...
        path = where(src)
        if path.is_file() and path.suffix.lower() in ui_files.ALLOWED_EXT:
            return f"[{m.group(1)}]({shown(path)})"
        return m.group(0)

    text = _MD_IMAGE.sub(keep, text)
    text = re.sub(r"(?<!!)\[([^\]]*)\]\(([^)\s]+)\)", link, text)
    return text.strip()


HINT_MARK = "[progress hint]"  # marks a nudge to the model that is not part of what the conversation remembers


class Docs:
    """The pages this task has retrieved, each with a number. The model cites [@N]; the number turns into the page's real link afterwards,
    so a source can only be a page that was actually returned or opened."""

    def __init__(self) -> None:
        self.by_url: dict[str, int] = {}
        self.rows: list[tuple[str, str]] = []

    def number(self, url: str, title: str = "") -> int:
        key = re.sub(r"[?&]utm_source=openai(?=&|#|$)", "", url).strip()
        if key not in self.by_url:
            self.rows.append((key, title.strip()))
            self.by_url[key] = len(self.rows)
        elif title and not self.rows[self.by_url[key] - 1][1]:
            self.rows[self.by_url[key] - 1] = (key, title.strip())
        return self.by_url[key]

    def link(self, text: str) -> str:
        """[@3] -> [site](url); [@3, @5] -> two links; a number that was never handed out is marked, not guessed."""
        def one(n: int) -> str:
            if not 1 <= n <= len(self.rows):
                return ""  # a number nobody was given is dropped, not shown to the reader
            url = self.rows[n - 1][0]
            host = re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
            return f"[{host}]({url})"

        def many(m: re.Match) -> str:
            return " ".join(one(int(x)) for x in re.findall(r"\d+", m.group(1)))

        return re.sub(r"\[(@\d+(?:\s*[,，、;；]\s*@?\d+)*)\]", many, text)


def expand_batches(output: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One web_search with `queries` (or read_webpage with `urls`) becomes several ordinary calls, so the run-side-by-side path handles them."""
    out: list[dict[str, Any]] = []
    for it in output:
        if it.get("type") == "function_call" and it.get("name") in ("web_search", "read_webpage"):
            key, many = ("query", "queries") if it.get("name") == "web_search" else ("url", "urls")
            try:
                args = json.loads(it.get("arguments") or "{}")
            except ValueError:
                args = {}
            values = [str(v).strip() for v in ([args.get(key)] if args.get(key) else []) + list(args.get(many) or []) if str(v).strip()]
            values = list(dict.fromkeys(values))
            if len(values) > 1:
                for n, v in enumerate(values):
                    out.append({**it, "call_id": f"{it.get('call_id')}-{n}", "arguments": json.dumps({"title": args.get("title") or "", key: v}, ensure_ascii=False)})
                continue
            if values and not args.get(key):  # a single value given in the list form
                out.append({**it, "arguments": json.dumps({"title": args.get("title") or "", key: values[0]}, ensure_ascii=False)})
                continue
        out.append(it)
    return out


# The fast database and literature functions (1-3 s each): offered as direct tools, so they run in the same batch as web_search.
DIRECT_NAMES = ("clinical_trials", "fda_adverse_events", "chembl_target_compounds", "open_targets", "target_tractability", "uniprot_lookup",
                "gtex_expression", "gnomad_constraint", "geo_search", "string_interactions", "reactome_pathways",
                "pubmed_search", "europepmc_search", "paper_abstracts", "civic_gene_variants",
                "ensembl_gene", "pdb_structures", "alphafold_structure", "pubchem_compound", "openalex_works")


# Words in a question that call for each direct tool. A tool is offered only when the question names its kind of data (the rest are
# still reachable through find_tools), so a call carries a few tool specs, not all of them.
DIRECT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "gnomad_constraint": ("gnomad", "pli", "loeuf", "约束", "constraint", "missense", "lof"),
    "clinical_trials": ("临床试验", "clinical trial", "clinicaltrials", "nct", "trial", "登记"),
    "fda_adverse_events": ("不良反应", "不良事件", "adverse", "faers", "openfda", "药物安全"),
    "chembl_target_compounds": ("chembl", "化合物", "compound", "ic50", "活性", "抑制剂"),
    "open_targets": ("open targets", "opentargets", "靶点", "疾病关联", "关联疾病", "target-disease"),
    "target_tractability": ("成药", "tractab", "druggab", "可成药"),
    "uniprot_lookup": ("uniprot", "蛋白", "protein", "功能域", "亚细胞"),
    "gtex_expression": ("gtex", "表达", "expression", "组织表达"),
    "geo_search": ("geo", "表达数据集", "gds", "数据集检索"),
    "string_interactions": ("string", "相互作用", "互作", "interaction", "partner"),
    "reactome_pathways": ("reactome", "通路", "pathway"),
    "pubmed_search": ("pubmed", "文献", "论文", "综述", "review", "paper", "pmid", "发表"),
    "europepmc_search": ("europe pmc", "europepmc", "preprint", "预印本", "文献", "论文", "综述"),
    "paper_abstracts": ("摘要", "abstract", "pmid", "doi", "论文", "文献"),
    "civic_gene_variants": ("civic", "肿瘤变异", "somatic", "体细胞", "cancer variant"),
}
_BOILERPLATE = re.compile(r"^(?:Direct call of a fast database or literature function \(1-3 s\)\.\s*)?(?:Database tool \(a fast direct call, 1-3 s\)\.\s*)?")


def _short(text: str, limit: int = 170) -> str:
    """The first sentences of a tool description, without the boilerplate that every direct tool repeats."""
    text = " ".join(_BOILERPLATE.sub("", " ".join(str(text or "").split())).split())
    cut = text[:limit]
    if len(text) > limit and ". " in cut:
        cut = cut[: cut.rindex(". ") + 1]
    return cut


@functools.lru_cache(maxsize=1)
def _all_direct_specs() -> tuple[dict[str, Any], ...]:
    """One function spec per direct tool, built from the same schema the registry uses (so names and parameters cannot drift)."""
    from biomni_ui import fast_tools

    out: list[dict[str, Any]] = []
    for s in fast_tools.SCHEMAS:
        if s.get("name") not in DIRECT_NAMES:
            continue
        req = s.get("required_parameters") or []
        props: dict[str, Any] = {"title": {"type": "string", "description": "A short human title of this step, in the user's language."}}
        required = ["title"]
        for p in req + (s.get("optional_parameters") or []):
            props[p["name"]] = {"type": "integer" if p.get("type") == "int" else "string", "description": str(p.get("description") or p["name"])[:80]}
            if p in req:
                required.append(p["name"])
        out.append({"type": "function", "name": s["name"], "description": _short(s.get("description")),
                    "parameters": {"type": "object", "properties": props, "required": required, "additionalProperties": False}})
    return tuple(out)


def direct_specs(question: str | None = None) -> list[dict[str, Any]]:
    """The direct tools for this call: all of them when no question is given, otherwise those whose keywords the question contains."""
    from biomni_ui import connectors

    specs = [s for s in _all_direct_specs() if connectors.enabled(str(s.get("name")))]  # a switched-off database is not offered
    if question is None:
        return specs
    q = question.lower()
    wanted = {name for name, words in DIRECT_KEYWORDS.items() if any(w in q for w in words)}
    return [s for s in specs if s["name"] in wanted]



_PARALLEL = ("web_search", "read_webpage", "search_literature", "find_tools", "run_tool") + DIRECT_NAMES  # lookups that do not touch the files or the Python session


def _fetch_one(fc: dict[str, Any]) -> Any:
    """Do one lookup (no events, no shared state), for running several at once. Returns what the sequential step needs."""
    try:
        args = json.loads(fc.get("arguments") or "{}")
    except ValueError:
        args = {}
    name = fc.get("name")
    try:
        if name == "web_search":
            from biomni_ui import web

            try:
                return web.search_rows(str(args.get("query") or "").strip(), 8)
            except Exception as e:
                return [], [], [f"{type(e).__name__}: {str(e)[:120]}"]
        if name == "read_webpage":
            from biomni_ui import web

            return web.read_webpage(str(args.get("url") or "").strip())
        if name == "search_literature":
            return run_literature(str(args.get("query") or ""))
        if name == "find_tools":
            from biomni_ui import biomni_tools

            return biomni_tools.find_tools(str(args.get("query") or ""))
        if name == "run_tool":
            from biomni_ui import biomni_tools

            return biomni_tools.run_tool(str(args.get("name") or "").strip(), args.get("arguments") if isinstance(args.get("arguments"), dict) else {})
        if name in DIRECT_NAMES:
            from biomni_ui import biomni_tools

            return biomni_tools.run_tool(str(name), {k: v for k, v in args.items() if k != "title"})
    except Exception as e:  # reported to the model like any failed step
        return f"{name} failed: {type(e).__name__}: {str(e)[:200]}"
    return None


class _Done:
    """A result that is already known (a refused call): same interface as _Later."""

    def __init__(self, value: Any):
        self._value = value

    def result(self) -> Any:
        return self._value


def _gated_tool(fc: dict[str, Any]) -> str | None:
    """The database connector a call would query, or None for calls that are not database calls."""
    from biomni_ui import connectors

    name = str(fc.get("name") or "")
    if name == "run_tool":  # called by name: the tool is in the arguments
        try:
            name = str(json.loads(fc.get("arguments") or "{}").get("name") or "").strip()
        except ValueError:
            return None
    return name if connectors.group_of(name) else None


class _Later:
    """One lookup running on its own thread; .result() waits for it."""

    def __init__(self, fn: Callable[..., Any], *args: Any):
        self._done = threading.Event()
        self._value: Any = None

        def work() -> None:
            try:
                self._value = fn(*args)
            except Exception as e:  # reported to the model like any failed step
                self._value = f"Error: {type(e).__name__}: {str(e)[:200]}"
            self._done.set()

        threading.Thread(target=work, daemon=True).start()

    def result(self) -> Any:
        self._done.wait()
        return self._value


class SubPool:
    """The sub-agents of one run. Each runs on its own thread, at most `workers` at once (the rest queue), while the main loop goes on.
    A result is handed over once: `ready()` gives the ones that have finished, `wait()` blocks until the chosen ones have finished."""

    def __init__(self, workers: int):
        from concurrent.futures import ThreadPoolExecutor

        self._ex = ThreadPoolExecutor(max_workers=max(1, int(workers or 1)), thread_name_prefix="sub-agent")
        self._jobs: dict[str, dict[str, Any]] = {}
        self._count = 0
        self._lock = threading.Lock()
        self.stopped = False  # set when the run ends: running sub-agents stop at their next step

    def start(self, fn: Callable[[], str], task: str, title: str) -> str:
        """Queue one sub-agent; returns the text the main agent sees at once."""
        with self._lock:
            self._count += 1
            sid = f"sub-{self._count}"
            self._jobs[sid] = {"task": " ".join(task.split())[:200], "future": self._ex.submit(fn), "delivered": False}
        return (f"Started sub-agent {sid} for “{title or task[:60]}”. It runs in parallel with you, and its result arrives as a message when it finishes. "
                "Keep working on the steps that do not need it; call wait_subagents only when you need its result now.")

    def pending(self) -> bool:
        with self._lock:
            return any(not j["delivered"] for j in self._jobs.values())

    def _text(self, job: dict[str, Any]) -> str:
        fut = job["future"]
        if fut.cancelled():
            return "[sub-agent cancelled before it started]"
        try:
            return str(fut.result())
        except Exception as e:  # reported like any finished result: the run goes on
            return f"[sub-agent failed: {type(e).__name__}]"

    def _take(self, ids: list[str] | None, only_done: bool) -> list[tuple[str, str, str]]:
        """The results of the chosen sub-agents that are not delivered yet, marked delivered. Unknown ids are ignored."""
        out = []
        with self._lock:
            for sid, job in self._jobs.items():
                if job["delivered"] or (ids is not None and sid not in ids):
                    continue
                if only_done and not job["future"].done():
                    continue
                job["delivered"] = True
                out.append((sid, job["task"], self._text(job)))
        return out

    def ready(self) -> list[tuple[str, str, str]]:
        """The results that have finished since the last call (never blocks)."""
        return self._take(None, only_done=True)

    def wait(self, ids: list[str] | None, cancel: Callable[[], bool]) -> list[tuple[str, str, str]]:
        """Block until the chosen sub-agents (all of them when ids is None) have finished, or the run is cancelled; returns their results."""
        from concurrent.futures import wait as wait_futures

        while not cancel() and not self.stopped:
            with self._lock:
                running = [j["future"] for _sid, j in self._selected(ids) if not j["future"].done()]
            if not running:
                break
            wait_futures(running, timeout=0.5)
        out = []
        with self._lock:
            for sid, job in self._selected(ids):
                if job["future"].done():
                    job["delivered"] = True  # asked for by name: returned even if it was already passed on as a message
                    out.append((sid, job["task"], self._text(job)))
        return out

    def _selected(self, ids: list[str] | None) -> list[tuple[str, dict[str, Any]]]:
        """Named sub-agents (even if already delivered), or, with no names, those not yet delivered. Call with the lock held."""
        return [(sid, j) for sid, j in self._jobs.items() if (ids is None and not j["delivered"]) or (ids is not None and sid in ids)]

    def close(self) -> None:
        self.stopped = True
        self._ex.shutdown(wait=False, cancel_futures=True)


def results_message(found: list[tuple[str, str, str]]) -> dict[str, Any]:
    """The finished sub-agent results as one message for the main agent."""
    blocks = [f"### {sid} — {task}\n{text}" for sid, task, text in found]
    return {"type": "message", "role": "user", "content": [{"type": "input_text", "text": (
        "Sub-agent results (they finished while you worked; use them in your answer, and say where a result is missing):\n\n" + "\n\n".join(blocks))}]}


def run(*, session: str | None = None, **kw: Any) -> tuple[str, list[dict[str, Any]], int]:
    """Drive the loop (see _run_loop). `session` names the Python session the `python` tool keeps (the conversation id: variables and
    imports survive between questions); without one the session lives only for this call."""
    from biomni_ui import pykernel

    own = session is None
    sess = session or f"run-{time.time_ns()}"
    try:
        return _run_loop(sess=sess, **kw)
    finally:
        if own:
            pykernel.POOL.close(sess)


def _run_loop(*, max_parallel: int = 3, allow_subagents: bool = True, **kw: Any) -> tuple[str, list[dict[str, Any]], int]:
    """The agent loop (see _run_loop_body). Sub-agents started in it run in a pool that is stopped when the loop ends, however it ends."""
    pool = SubPool(max_parallel) if allow_subagents else None
    try:
        return _run_loop_body(pool=pool, allow_subagents=allow_subagents, **kw)
    finally:
        if pool is not None:
            pool.close()


def _run_loop_body(*, sess: str, model: str, effort: str, question: str, history: list[dict[str, Any]], instructions: str, emit: Callable[[dict[str, Any]], None],
                   cancel: Callable[[], bool], cwd: Path, load_skill: Callable[[str], str] | None = None, find_skill: Callable[[str], str] | None = None, on_text: Callable[[str], None] | None = None,
                   nudge: Callable[[str, int], str | None] | None = None, escalate_to: str | None = None, call: Callable[..., Any] = call_model,
                   tools_fn: Callable[[], list[dict[str, Any]]] | None = None, mid_effort: str | None = None, allow_ask: bool = True,
                   max_steps: int | None = None, project_id: str | None = None,
                   permit: Callable[[str, str], str] | None = None, delegate_model: str | None = None,
                   delegate_call: Callable[..., Any] | None = None, delegate_effort: str | None = None,
                   image_call: Callable[[str, str], str] | None = None, pool: "SubPool | None" = None,
                   allow_subagents: bool = True, checkpoint: Callable[[list[dict[str, Any]]], None] | None = None) -> tuple[str, list[dict[str, Any]], int]:
    """Returns (answer, items to remember, number of steps taken). `nudge(answer, steps)` may return a message that
    sends the model back to work (an answer that gave up too early). Sub-agents asked for in one round run side by side (at most
    `max_parallel` at once) while this loop's own commands and lookups carry on. `image_call(path, question)` is offered as the
    look_at_image tool when the image model is set."""
    from biomni_ui import chatgpt_api as c
    from biomni_ui import pykernel, workdir

    items = [*history, {"type": "message", "role": "user", "content": [{"type": "input_text", "text": question}]}]
    steps = 0
    nudges = 0
    enough = False  # the same call keeps repeating: no more tools
    hinted = False  # the judge's "may be enough" was passed on to the model once
    batches = 0
    planned = False
    judging = None  # the sufficiency judge runs beside the next model call, so it adds no waiting
    used: dict[str, str] = {}  # the tools this task has used so far
    know: list[str] = []  # skills loaded and specialist functions consulted
    last_report = [""]

    def report() -> None:
        """Tell the page which tools and which knowledge this task has used so far (the two panels on the right)."""
        payload = {"type": "tools", "tools": list(used), "libraries": [], "data_lake": [], "know_how": list(know)}
        key = json.dumps(payload, ensure_ascii=False)
        if key != last_report[0]:
            last_report[0] = key
            emit(payload)
    def offered(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        tools = [t for t in tools if t.get("name") not in ("look_at_image", "wait_subagents")]
        tools += [LOOK_SPEC] if image_call is not None else []  # the picture tool only when an image model is set
        tools += [WAIT_SPEC] if pool is not None else []  # waiting for sub-agents only where they can run
        if not allow_subagents:
            tools = [t for t in tools if t.get("name") != "delegate_task"]
        return tools if allow_ask else [t for t in tools if t.get("name") != "ask_user"]  # the question tool is offered only when the mode allows it

    docs = Docs()
    seen_calls: dict[str, int] = {}
    stuck = 0
    while True:  # no step limit: the loop ends when the model answers, the judge says enough, the user stops it, or it is going round in circles
        if cancel():
            return "", items, steps
        if max_steps is not None and steps >= max_steps:
            enough = True  # a capped run (a sub-agent) has used its steps: the next round is an answer, with no more tools
        if checkpoint is not None:  # what has happened so far is kept, so a cut-off task can be continued
            checkpoint(items)
        if pool is not None:
            finished = pool.ready()  # sub-agents that finished meanwhile reach the model before its next round
            if finished:
                items.append(results_message(finished))
        # One level for every call on the answer path: the chosen level, never below the starting tier (see effort.FLOOR).
        worked = any(i.get("type") == "function_call_output" for i in items[len(history):])
        now = (mid_effort or effort) if worked and not nudges else effort
        output, meta = call(model, now, instructions, shrink_view(items), [] if enough else offered((tools_fn or active_tools)()), on_text)
        if judging is not None:
            try:
                done, why = judging.result()
            except Exception:
                done, why = False, ""
            judging = None
            if done and not hinted:  # the judge thinks this is enough: say so once; the model decides, with its tools still in hand
                hinted = True
                if any(i.get("type") == "function_call" for i in output):  # the call that ran beside the judge wanted more tools: drop it and let the model reconsider
                    emit({"type": "notice", "text": "The judge thinks the material may already be enough; the agent will check it against your request once more." + (f" ({why})" if why else "")})
                    items.append({"type": "message", "role": "user", "content": [{"type": "input_text", "text": (
                        HINT_MARK + "The assessment says the material may already be enough. Check the user's exact words: if every item the user asked for (content, files, figures, sequences, each question) is already there, give the sourced answer directly, "
                        "write “not retrieved” for anything not found. If something the user explicitly asked for is still missing, say what is missing and keep going; do not hand in a half-finished result just to save time.")}]})
                    continue
        usage = meta.get("usage") or {}
        emit({"type": "llm", "model": model, "effort": now, "seconds": meta.get("seconds", 0), "input_tokens": usage.get("input_tokens"),
              "output_tokens": usage.get("output_tokens"), "reasoning_tokens": (usage.get("output_tokens_details") or {}).get("reasoning_tokens"),
              "calls": sum(1 for i in output if i.get("type") == "function_call")})
        output = expand_batches(output)
        items.extend(output)
        searches = [i.get("action") or {} for i in output if i.get("type") == "web_search_call"]
        for card in c.search_activity(searches):
            steps += 1
            emit({"type": "tool", **card})
            used.setdefault("web_search", "")
            workdir.add_references(cwd, str(card.get("query") or ""), card.get("results") or [])
            workdir.add_note(cwd, f"**Web search**: {card.get('query')}\n\n" + "\n".join(f"- {r.get('url')}" for r in (card.get("results") or [])[:8]))
        calls = [i for i in output if i.get("type") == "function_call"]
        said = "\n".join(t for t in (message_text(i) for i in output if i.get("type") == "message") if t)
        asks = [fc for fc in calls if fc.get("name") == "ask_user"] if allow_ask else []
        if asks:  # a choice only the user can make: nothing else in this turn runs; the page shows the options and the pick comes back as the next message
            try:
                args = json.loads(asks[0].get("arguments") or "{}")
            except ValueError:
                args = {}
            question = str(args.get("question") or "").strip() or "Please choose the next step."
            options = [str(x).strip() for x in (args.get("options") or []) if str(x).strip()][:4]
            for fc in calls:
                items.append({"type": "function_call_output", "call_id": fc.get("call_id"), "output": "The choice question was handed to the user and is waiting for an answer; the other calls in this round were not run."})
            emit({"type": "ask", "question": question, "options": options})
            report()
            text = (said + "\n\n" if said else "") + question
            return clean_answer(docs.link(text), cwd), [i for i in items if not (i.get("type") == "message" and HINT_MARK in message_text(i))], steps
        if not calls and pool is not None and pool.pending():
            # the answer waits for the sub-agents that are still running, and they go to the model together with the answer's draft
            if cancel():
                return "", items, steps
            waited = pool.wait(None, cancel)
            if waited:
                items.append(results_message(waited))
                continue
        if not calls:
            if not said:
                return "", items, steps
            if nudge:
                more = nudge(said, steps)
                if more and nudges < 2:
                    nudges += 1
                    effort = escalate_to or effort  # the easy route failed: think at the full setting from here on
                    emit({"type": "notice", "text": more[1] if isinstance(more, tuple) else "The agent was asked to continue."})
                    items.append({"type": "message", "role": "user", "content": [{"type": "input_text", "text": more[0] if isinstance(more, tuple) else more}]})
                    continue
            pre, said = split_preambles(said)
            if pre:
                emit({"type": "reasoning", "text": pre})
            report()
            return clean_answer(docs.link(said), cwd), [i for i in items if not (i.get("type") == "message" and HINT_MARK in message_text(i))], steps
        if said:
            emit({"type": "reasoning", "text": said})
        # Lookups (searches, page reads, tool calls) start together and run while the commands and Python steps of the same turn work through
        # in order (they share the files and the Python session); each card appears in order once its result is in.
        lookups = [fc for fc in calls if fc.get("name") in _PARALLEL]
        refused: dict[str, str] = {}
        if permit is not None:  # a database connector needs the user's permission (or a standing grant) before it is queried
            for fc in lookups:
                tool = _gated_tool(fc)
                if tool and permit(tool, str(fc.get("call_id"))) != "allow":
                    refused[str(fc.get("call_id"))] = (f"The user did not allow the database “{tool}” for this request, so it was not queried. "
                                                      "Carry on without it, or say what is missing.")
        futures = {str(fc.get("call_id")): (_Done(refused[str(fc.get("call_id"))]) if str(fc.get("call_id")) in refused else _Later(_fetch_one, fc)) for fc in lookups}
        shell = [fc for fc in calls if fc.get("name") == "bash"]
        if len(shell) > 1:  # several commands in one turn were asked for together: they are independent, so they run together
            for fc in shell:
                try:
                    cmd = str(json.loads(fc.get("arguments") or "{}").get("command") or "")
                except ValueError:
                    cmd = ""
                lookups.append(fc)
                futures[str(fc.get("call_id"))] = _Later(run_bash, cmd, cwd, cancel)

        # Sub-agents asked for in this round start now, side by side (at most max_parallel at once), and run while the commands and lookups
        # of the round work through in order; their results come back in the order the model asked for them.
        def run_delegate(fc: dict[str, Any], args: dict[str, Any]) -> str:
            """One sub-agent, run to its end (in the pool's thread, or here when sub-agents are not allowed)."""
            task_text = str(args.get("task") or "")
            title = str(args.get("title") or "").strip()
            emit({"type": "code", "language": "text", "code": (f"# {title}\n" if title else "") + f"delegate_task({task_text[:200]!r})"})
            # the sub-agent runs on its own model when one is chosen in Settings, otherwise on the same model as this task, at its own effort
            return _delegate(task_text, str(args.get("context") or ""), model=delegate_model or model, effort=delegate_effort or effort, instructions=instructions,
                             cancel=lambda: cancel() or (pool is not None and pool.stopped), cwd=cwd, load_skill=load_skill, find_skill=find_skill,
                             call=delegate_call or call, permit=permit, emit=emit)

        class _Ahead(dict):
            def __contains__(self, key):
                return key in futures

            def __getitem__(self, key):
                return futures[key].result()

            def get(self, key, default=None):
                return futures[key].result() if key in futures else default

        ahead = _Ahead()
        first_out = len(items)
        for fc in [c for c in calls if str(c.get("call_id")) not in futures] + lookups:  # commands first, so they work while the lookups are out
            steps += 1
            try:
                args = json.loads(fc.get("arguments") or "{}")
            except ValueError:
                args = {}
            sig = f"{fc.get('name')}:{json.dumps(args, sort_keys=True, ensure_ascii=False)}"
            seen_calls[sig] = seen_calls.get(sig, 0) + 1
            if seen_calls[sig] >= 4 and fc.get("name") != "todo":  # the same call a fourth time gives the same result: going round in circles
                stuck += 1
                steps -= 1
                if stuck >= 2:
                    enough = True
                items.append({"type": "function_call_output", "call_id": fc.get("call_id"), "output": "You have already made this call 3 times and the result will not change. Use another method, or answer from the material you have (write \"not retrieved\" for anything you could not find)."})
                continue
            title = str(args.get("title") or "").strip()
            t0 = time.time()
            made: list[str] = []
            before = snapshot(cwd) if fc.get("name") in ("bash", "python") else None
            if fc.get("name") in ("bash", "python", "read_webpage", "web_search", "todo", "use_skill", "search_literature", "find_tools", "run_tool", "find_skills") or fc.get("name") in DIRECT_NAMES:
                used.setdefault(str(fc.get("name")), "")
                if fc.get("name") != "todo" and fc.get("name") not in DIRECT_NAMES:
                    usage_stats.store().bump("tool", str(fc.get("name")))
            if fc.get("name") in ("bash", "python"):
                for fn_name, fn_doc in biomni_functions_in(str(args.get("command") or args.get("code") or "")).items():
                    used.setdefault(fn_name, fn_doc)
                    usage_stats.store().bump("func", fn_name)
                    note = f"{fn_name}: {fn_doc[:90]}"
                    if note not in know:
                        know.append(note)
            if fc.get("name") in ("bash", "python", "read_webpage"):  # the databases and pages a step reached: knowledge consulted
                for host in dict.fromkeys(re.findall(r"https?://([A-Za-z0-9.-]+)", str(args.get("command") or args.get("code") or args.get("url") or ""))):
                    host_note = f"Data source / web page: {host}"
                    if host_note not in know and len(know) < 16:
                        know.append(host_note)
            if fc.get("name") == "use_skill":
                usage_stats.store().bump("skill", str(args.get("name") or "").strip())
                skill_note = f"Skill: {str(args.get('name') or '').strip()}"
                if skill_note not in know:
                    know.append(skill_note)
            if fc.get("name") == "todo":
                steps -= 1  # a plan is bookkeeping, not work: it must not count as a step the answer rests on
                plan = todo_steps(args.get("items"))
                if plan:
                    planned = True
                    emit({"type": "plan", "steps": plan})
                    workdir.add_note(cwd, "**Plan**\n\n" + "\n".join(f"- [{'x' if x['status'] == 'done' else ' '}] {x['text']}" for x in plan))
                items.append({"type": "function_call_output", "call_id": fc.get("call_id"), "output": "Todo list updated."})
                continue
            if fc.get("name") == "bash":
                command = str(args.get("command") or "")
                emit({"type": "code", "language": "bash", "code": (f"# {title}\n" if title else "") + command})
                result = ahead.get(str(fc.get("call_id"))) if str(fc.get("call_id")) in ahead else run_bash(command, cwd, cancel)
            elif fc.get("name") == "python":
                code = str(args.get("code") or "")
                emit({"type": "code", "language": "python", "code": (f"# {title}\n" if title else "") + code})
                from biomni_ui import permissions  # database calls made from this Python step are answered here, while it runs
                serving = threading.Event()
                threading.Thread(target=permissions.serve, args=(sess, lambda tool: permit(tool, "python") if permit is not None else "allow", serving), daemon=True).start()
                try:
                    result = pykernel.run(sess, code, cwd, cancel)
                finally:
                    serving.set()
                if "cannot import name" in result and "find_tools" in result:  # imported from the wrong module: it is already in the session
                    result += "\n" + "Note: find_tools is already preloaded in python; call find_tools('English keywords') directly, with no import."
            elif fc.get("name") == "web_search":
                from biomni_ui import web

                query = str(args.get("query") or "").strip()
                try:
                    rows, engines, errors = ahead[str(fc.get("call_id"))] if str(fc.get("call_id")) in ahead else web.search_rows(query, 8)
                except Exception as e:  # reported to the model like any failed step
                    rows, engines, errors = [], [], [f"{type(e).__name__}: {str(e)[:120]}"]
                used.setdefault("web_search", "")
                result = web.format_results(query, rows, engines, errors, number=docs.number)
                card = {"tool": "web_search", "query": query, "text": "",
                        "results": [{"title": r["title"], "url": r["url"], "domain": r["site"], "snippet": r["snippet"][:200]} for r in rows]}
                emit({"type": "tool", **card})
                workdir.add_references(cwd, query, card["results"])
                workdir.add_note(cwd, f"**Web search**: {query}" + chr(10) * 2 + chr(10).join(f"- {r['url']}" for r in rows[:8]))
                _receipt(cwd, fc, args, result, t0)
                items.append({"type": "function_call_output", "call_id": fc.get("call_id"), "output": result})
                continue  # the search card shows the results; no extra observation card
            elif fc.get("name") == "read_webpage":
                from biomni_ui import web

                url = str(args.get("url") or "").strip()
                emit({"type": "code", "language": "python", "code": (f"# {title}\n" if title else "") + f"read_webpage({url!r})"})
                result = ahead.get(str(fc.get("call_id"))) if str(fc.get("call_id")) in ahead else web.read_webpage(url)
                if url.startswith("http") and not str(result).startswith(("Could not read the web page", "This link is not a web page")):
                    title_line = re.match("Title: (.*)", str(result))
                    result = f"[@{docs.number(url, title_line.group(1) if title_line else '')}] cite this page as [@N]" + chr(10) + str(result)
            elif fc.get("name") in DIRECT_NAMES:
                from biomni_ui import biomni_tools

                arguments = {k: v for k, v in args.items() if k != "title"}
                emit({"type": "code", "language": "python", "code": (f"# {title}\n" if title else "") + f"{fc.get('name')}({json.dumps(arguments, ensure_ascii=False)})"})
                result = ahead.get(str(fc.get("call_id"))) if str(fc.get("call_id")) in ahead else biomni_tools.run_tool(str(fc.get("name")), arguments)
                usage_stats.store().bump("func", str(fc.get("name")))
            elif fc.get("name") == "propose_memory":
                from biomni_ui import notes

                emit({"type": "code", "language": "text", "code": (f"# {title}\n" if title else "") + "propose_memory (waits for the user's approval)"})
                try:
                    notes.propose(str(args.get("text") or ""), project_id)
                    result = "Suggested to the user's memory. It is used only after they approve it in Settings."
                except Exception as e:  # reported to the model like any failed step
                    result = f"Could not save the suggestion ({type(e).__name__})."
            elif fc.get("name") == "delegate_task":
                if pool is None:  # sub-agents are not allowed in this run
                    result = "Sub-agents are not available here; do this step yourself."
                else:  # it starts now and runs beside this loop; its result arrives as a message
                    result = pool.start(lambda fc=fc, args=args: run_delegate(fc, args), str(args.get("task") or ""), title)
            elif fc.get("name") == "wait_subagents":
                raw_ids = args.get("ids")
                ids = [str(x).strip() for x in raw_ids if str(x).strip()] if isinstance(raw_ids, list) and raw_ids else None
                emit({"type": "code", "language": "text", "code": (f"# {title}\n" if title else "") + f"wait_subagents({ids or 'all'})"})
                found = pool.wait(ids, cancel) if pool is not None else []
                result = (results_message(found)["content"][0]["text"] if found else "No sub-agent has finished that you asked for, or none is running.")
            elif fc.get("name") == "look_at_image":
                path = str(args.get("path") or "")
                question = str(args.get("question") or "")
                emit({"type": "code", "language": "text", "code": (f"# {title}\n" if title else "") + f"look_at_image({path!r})"})
                try:
                    result = image_call(path, question) if image_call is not None else "No image model is set in Settings."
                except Exception as e:  # reported to the model like any failed step
                    result = f"Could not look at the picture: {str(e)[:300]}"
            elif fc.get("name") == "find_skills":
                query = str(args.get("query") or "")
                emit({"type": "code", "language": "text", "code": f"# {title}" + chr(10) + f"find_skills({query!r})"})
                result = find_skill(query) if find_skill else "No skill library."
            elif fc.get("name") == "use_skill":
                sid = str(args.get("name") or "").strip()
                emit({"type": "code", "language": "text", "code": f"# Load skill {sid}\nuse_skill({sid!r})"})
                result = (load_skill(sid) if load_skill else "") or f"No such skill: {sid}. Choose one from the catalogue."
            elif fc.get("name") == "search_literature":
                query = str(args.get("query") or "")
                emit({"type": "code", "language": "python", "code": (f"# {title}\n" if title else "") + f"search_literature({query!r})"})
                result = ahead.get(str(fc.get("call_id"))) if str(fc.get("call_id")) in ahead else run_literature(query)
            elif fc.get("name") == "find_tools":
                from biomni_ui import biomni_tools

                query = str(args.get("query") or "")
                emit({"type": "code", "language": "python", "code": (f"# {title}\n" if title else "") + f"find_tools({query!r})"})
                result = ahead.get(str(fc.get("call_id"))) if str(fc.get("call_id")) in ahead else biomni_tools.find_tools(query)
            elif fc.get("name") == "run_tool":
                from biomni_ui import biomni_tools

                tool = str(args.get("name") or "").strip()
                arguments = args.get("arguments") if isinstance(args.get("arguments"), dict) else {}
                emit({"type": "code", "language": "python", "code": (f"# {title}\n" if title else "") + f"run_tool({tool!r}, {json.dumps(arguments, ensure_ascii=False)})"})
                result = ahead.get(str(fc.get("call_id"))) if str(fc.get("call_id")) in ahead else biomni_tools.run_tool(tool, arguments)
            else:
                emit({"type": "code", "language": "text", "code": str(fc.get("name"))})
                result = f"No such tool: {fc.get('name')}"
            if before is not None:
                made = changed_files(before, snapshot(cwd))
                workdir.add_step(cwd, "bash" if fc.get("name") == "bash" else "python", title, str(args.get("command") or args.get("code") or ""), result)
            receipt = _receipt(cwd, fc, args, result, t0, made)
            emit({"type": "observation", "text": result, "files": made, "elapsed": round(time.time() - t0, 2), **({"receipt": receipt} if receipt else {})})
            items.append({"type": "function_call_output", "call_id": fc.get("call_id"), "output": result})
        order = {str(c.get("call_id")): n for n, c in enumerate(calls)}
        items[first_out:] = sorted(items[first_out:], key=lambda i: order.get(str(i.get("call_id")), 0))  # the model gets the results in the order it asked
        report()
        batches += 1
        if not enough and not hinted and batches >= 2 and not cancel():
            from concurrent.futures import ThreadPoolExecutor

            snapshot_items = list(items)
            judging = ThreadPoolExecutor(max_workers=1).submit(judge_enough, call, model, EFFORT_FLOOR if call is call_model else "judge", question, snapshot_items)
        if cancel():
            return "", items, steps
