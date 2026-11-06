"""Checks a community skill before it is added, in the way Hermes' skills guard does: the text is scanned for risky patterns, the scan gives a
verdict (safe, caution or dangerous), and the install policy depends on the verdict and on where the skill comes from.

The rules here are a deliberately small, readable set. They are not a guarantee: a skill is text the agent will follow, so the user still
reads it before relying on it. A dangerous verdict is never installed, even with force."""

from __future__ import annotations

import re
from typing import Any

# (pattern, severity, what it means). critical -> dangerous verdict; high -> caution; medium and low are noted but do not block.
RULES: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"\b(curl|wget)\b[^\n|]*\|\s*(sudo\s+)?(ba|z)?sh\b"), "critical", "downloads a script and runs it at once"),
    (re.compile(r"base64\s+(-d|--decode)[^\n]*\|\s*(ba)?sh\b"), "critical", "decodes hidden code and runs it"),
    (re.compile(r"\brm\s+-[a-z]*r[a-z]*f?\s+(/|~|\$HOME)(\s|$|/\*)"), "critical", "deletes files from the root or the home folder"),
    (re.compile(r"/dev/tcp/|\bnc\s+(-[a-z]*e|-e)\b"), "critical", "opens a remote shell"),
    (re.compile(r"(\.ssh/id_|\.aws/credentials|\.netrc|\.pgpass|\.env\b)[^\n]*(curl|wget|requests\.post|urlopen|httpx\.|http://|https://)"), "critical",
     "reads credentials and sends them somewhere"),
    (re.compile(r"(ignore|disregard|forget)\s+(all\s+|any\s+|the\s+)?(previous|prior|above|earlier)\s+(instructions|rules|messages)", re.I), "high",
     "tries to override the agent's own instructions"),
    (re.compile(r"\bsudo\b"), "high", "asks for administrator rights"),
    (re.compile(r"chmod\s+(-R\s+)?0?777\b"), "high", "makes files writable by everyone"),
    (re.compile(r"(?<![\w.])eval\s*\("), "medium", "evaluates text as code"),  # not model.eval(), which is a normal method call
    (re.compile(r"\bos\.system\(|subprocess\.\w+\([^\n]*shell\s*=\s*True"), "medium", "runs a shell command from Python"),
    (re.compile(r"\bpip\s+install\b|\bnpm\s+install\s+-g\b"), "low", "installs packages"),
]

VERDICT_RANK = {"safe": 0, "caution": 1, "dangerous": 2}


def scan(text: str) -> dict[str, Any]:
    """The verdict and the findings (line number, severity, rule and the line itself, shortened)."""
    findings = []
    for n, line in enumerate(str(text or "").splitlines(), start=1):
        for pattern, severity, meaning in RULES:
            if pattern.search(line):
                findings.append({"line": n, "severity": severity, "rule": meaning, "text": line.strip()[:160]})
    sev = {f["severity"] for f in findings}
    verdict = "dangerous" if "critical" in sev else "caution" if "high" in sev else "safe"
    return {"verdict": verdict, "findings": findings}


def decide(verdict: str, trust: str, force: bool = False) -> tuple[bool, str]:
    """Whether the install may go ahead, and why. Dangerous is never installed. Caution needs force, from a community source. Trusted sources
    may install caution; a safe verdict installs from any source."""
    if verdict == "dangerous":
        return False, "Blocked: the scan found a dangerous pattern. A dangerous verdict is never installed, even with force."
    if verdict == "caution" and not (force or trust == "trusted"):
        return False, "Needs your confirmation: the scan found risky patterns. Read them below, then install anyway if you trust this skill."
    if verdict == "caution":
        return True, "Installed: the scan found risky patterns and you confirmed it." if force else "Installed: a trusted source with risky patterns."
    return True, "Installed: no risky patterns found."
