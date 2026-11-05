"""Judge first, then decide how hard to think.

At the highest reasoning effort every model call takes 20-90 s, whatever the question. A weather lookup does not need that;
a literature synthesis does. A short low-effort call rates the task, and the agent starts at a matching effort. The effort
the user chose in the settings is the ceiling, and a guard correction (the model answered without working) puts the agent
back at the ceiling for the rest of the task.
"""

from __future__ import annotations

import json
import re
from typing import Any

ORDER = ("minimal", "low", "medium", "high", "xhigh", "max")  # reasoning levels, weakest first
FLOOR = "medium"  # the starting tier: nothing on the answer path thinks less than this. A lower level is not offered, and one already stored is raised to it


def floor(level: str) -> str:
    """The level raised to the starting tier when it is below it. A level this module does not know is returned as it is."""
    if level in ORDER and ORDER.index(level) < ORDER.index(FLOOR):
        return FLOOR
    return level


def offered(options: list[str]) -> list[str]:
    """The levels a user can pick: the provider's own, without any below the starting tier."""
    kept = [o for o in options if o not in ORDER or ORDER.index(o) >= ORDER.index(FLOOR)]
    return kept or ([FLOOR] if options else [])

ROUTER_SYSTEM = (
    "You judge how hard a task is. Read the question and output only JSON: {\"level\": \"simple|normal|deep\"}.\n"
    "simple: needs one fact, one definition or one value (weather, what a name refers to, which chromosome a gene is on, a simple calculation); no listing or synthesis of several sources.\n"
    "normal: needs listing, comparing or summarising several sources (\"which are there\", \"what is the difference\", \"mechanism\", \"progress\", \"current status\", e.g. the drugs for a target, the treatments for a disease, the clinical significance of a variant).\n"
    "deep: a literature review or evidence appraisal, statistics and data analysis, modelling, study design, cross-checking several databases, the user supplied files or data, or a question that needs exact numbers.\n"
    "If unsure, choose normal. Anything that involves the user's files or data analysis is always deep."
)

_MAP = {"simple": FLOOR, "normal": FLOOR}  # deep keeps the user's setting; a simple or normal question starts at the floor, not below it


def parse_level(text: str) -> str:
    try:
        a, b = text.find("{"), text.rfind("}") + 1
        level = json.loads(text[a:b]).get("level")
    except (ValueError, TypeError, AttributeError):
        return "deep"
    return level if level in ("simple", "normal", "deep") else "deep"


def effort_for(level: str, ceiling: str) -> str:
    """The effort to start at: never above the ceiling, never below the starting tier."""
    ceiling = floor(ceiling)
    want = floor(_MAP.get(level, ceiling))
    if want not in ORDER or ceiling not in ORDER:
        return ceiling
    return want if ORDER.index(want) < ORDER.index(ceiling) else ceiling


def pick(fast_llm: Any, question: str, ceiling: str, has_files: bool = False) -> tuple[str, str]:
    """(effort, level). Any trouble means the ceiling: judging must never make an answer worse than before."""
    from langchain_core.messages import HumanMessage, SystemMessage

    if has_files:
        return ceiling, "deep"
    try:
        reply = fast_llm.invoke([SystemMessage(content=ROUTER_SYSTEM), HumanMessage(content=question[:1500])])
        level = parse_level(reply.content if isinstance(reply.content, str) else str(reply.content))
    except Exception:
        return ceiling, "deep"
    return effort_for(level, ceiling), level


_DEEP = re.compile(r"分析|统计|差异|画图|绘图|作图|图表|代码|脚本|模拟|建模|拟合|聚类|富集|比对|引物|设计|优化|流程|pipeline|\.(?:csv|tsv|xlsx?|h5ad|fa|fasta|fastq|pdf|docx|vcf|bam)\b|上传|附件|我的(?:文件|数据)|analy[sz]e|statistic|differential|plot|chart|figure|code|script|simulat|model|fitting|cluster|enrich|align|primer|design|workflow|upload|attachment|my (?:file|data)", re.I)
_NORMAL = re.compile(r"有哪些|哪些|区别|比较|对比|总结|概括|综述|进展|现状|机制|耐药|临床意义|列出|介绍|作用|适应症|阶段|疗效|安全性|which|list|compare|difference|summari[sz]e|review|progress|status|mechanism|resistance|clinical significance|introduc|role|indication|phase|efficacy|safety", re.I)


def heuristic(question: str, has_files: bool = False) -> str:
    """simple | normal | deep from the wording alone: no model call, so nothing is added before the answer starts."""
    q = question or ""
    if has_files or _DEEP.search(q):
        return "deep"
    if len(q) > 80 or _NORMAL.search(q):
        return "normal"
    return "simple"
