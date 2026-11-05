"""Extra LLM calls around a finished task: a second-opinion review and follow-up suggestions."""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

MAX_TRANSCRIPT_CHARS = 14000

REVIEW_SYSTEM = """You are an independent scientific reviewer, checking a biomedical analysis that another agent has completed. Judge only from the execution record, and do not invent anything the record does not contain.
Check each of the five items below, giving a verdict (pass / doubtful / fail) and one or two specific reasons:
1. Data handling: whether the correct data were loaded, and whether filtering and preprocessing were sound
2. Method choice: whether the tools or methods used suit the question
3. Statistical reporting: whether significance, exact values and multiple-testing correction are appropriate (write "not applicable" if no statistics are involved)
4. Source reliability: whether the conclusions are backed by database returns or literature, and whether any claim has no source
5. Reasoning chain: whether the conclusions follow from the evidence, and whether limitations are stated
Finish with an "Overall judgement" (one sentence) and "Suggested improvements" (at most three). Reply in the user's language, in Markdown, concisely."""

SUGGEST_SYSTEM = """Based on the question and answer below, give 3 follow-up questions the user is most likely to ask next. Each must be no longer than 30 words, the three must not repeat each other, and each must be able to go deeper from the results already obtained. Write them in the user's language.
Output only a JSON array, for example ["question one","question two","question three"], with no other text."""


PLAN_SYSTEM = """You are the planner for a biomedical analysis agent. The user has set a research task. First decide whether it needs a multi-step plan, then give a draft plan.
Output only one JSON object with these fields:
- "simple": a boolean. true for a question that one query or one sentence can answer; false for a question that needs several retrieval, calculation or comparison steps.
- "questions": an array of at most 3 items. Ask only when key information is missing and work cannot start without it (species, dataset, comparison object, time range and so on), and keep each item to 40 characters or fewer; if the information is sufficient, give an empty array.
- "plan": an array of 3 to 6 concrete steps, each 40 characters or fewer, in the order they run. When simple is true, 1 or 2 steps are enough.
Write the questions and plan steps in the user's language. Output nothing except the JSON."""


def parse_plan(raw: str) -> dict[str, Any]:
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return {"simple": False, "questions": [], "plan": []}
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"simple": False, "questions": [], "plan": []}
    clean = lambda xs, n: [s.strip() for s in xs if isinstance(s, str) and s.strip()][:n] if isinstance(xs, list) else []
    return {"simple": bool(d.get("simple")), "questions": clean(d.get("questions"), 3), "plan": clean(d.get("plan"), 8)}


def draft_plan(llm, prompt: str, earlier: list[tuple[str, str]] | None = None) -> dict[str, Any]:
    ctx = "".join(f"[Earlier conversation]\nQ: {q}\nA: {a}\n\n" for q, a in (earlier or []))
    return parse_plan(_ask(llm, PLAN_SYSTEM, f"{ctx}[User task]\n{prompt}"))


def approved_prompt(prompt: str, plan: list[str], answers: list[tuple[str, str]]) -> str:
    """Text appended to the task so the agent follows the plan the user approved."""
    parts = []
    if answers:
        parts.append("The user's answers to the clarifying questions:\n" + "\n".join(f"- {q} → {a}" for q, a in answers if a.strip()))
    if plan:
        parts.append("The plan the user approved (follow it; if you must change it, say why):\n"
                     + "\n".join(f"{i}. [ ] {s}" for i, s in enumerate(plan, 1)))
    return "\n\n".join(parts)


def transcript(prompt: str, events: list[dict[str, Any]], earlier: list[tuple[str, str]] | None = None) -> str:
    """`earlier` holds (question, answer) pairs from previous turns of the same conversation."""
    parts = [f"[Earlier conversation]\nQ: {q}\nA: {a}" for q, a in (earlier or [])]
    parts.append(f"[User question]\n{prompt}")
    for e in events:
        t = e.get("type")
        if t == "plan":
            parts.append("[Plan]\n" + "\n".join(f"- [{s['status']}] {s['text']}" for s in e["steps"]))
        elif t == "reasoning":
            parts.append(f"[Reasoning]\n{e['text']}")
        elif t == "code":
            parts.append(f"[Code ({e['language']})]\n{e['code']}")
        elif t == "observation":
            parts.append(f"[Execution output]\n{e['text'][:1500]}")
        elif t == "answer":
            parts.append(f"[Final answer]\n{e['text']}")
    text = "\n\n".join(parts)
    if len(text) > MAX_TRANSCRIPT_CHARS:  # keep the head (question/plan) and the tail (answer)
        half = MAX_TRANSCRIPT_CHARS // 2
        text = text[:half] + "\n\n…(middle part omitted)…\n\n" + text[-half:]
    return text


def _ask(llm, system: str, user: str) -> str:
    out = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
    return out.content if isinstance(out.content, str) else str(out.content)


def review(llm, prompt: str, events: list[dict[str, Any]], earlier=None) -> str:
    return _ask(llm, REVIEW_SYSTEM, transcript(prompt, events, earlier)).strip()


def parse_suggestions(raw: str) -> list[str]:
    m = re.search(r"\[.*\]", raw, re.DOTALL)
    if not m:
        return []
    try:
        items = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    return [s.strip() for s in items if isinstance(s, str) and s.strip()][:4]


def suggest(llm, prompt: str, events: list[dict[str, Any]], earlier=None) -> list[str]:
    return parse_suggestions(_ask(llm, SUGGEST_SYSTEM, transcript(prompt, events, earlier)))
