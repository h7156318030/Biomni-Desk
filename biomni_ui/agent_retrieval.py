"""Trim the tool list the official agent's model-based selection step is given (a local keyword pre-filter).

The official agent asks its model to choose the tools for each task from the whole registry (about 50,000 characters of tool descriptions),
before it answers, so every task starts with a large model call. Here the registry is first narrowed on this machine: the tools whose names
and descriptions share words with the question come first, topped up with the tools the registry marks PREFERRED (the common ones), up to
TOP_K. When the question shares no word with any tool (for example a question with no English term in it), the whole list is passed on,
as before. The agent class is not changed.
"""

from __future__ import annotations

import re
from typing import Any

TOP_K = 30
TOP_LIBRARIES = 20  # the software libraries offered to the selection step
# Chinese terms in a question and the English words the tool descriptions use for them.
_CN_EN = {
    "基因": ["gene"], "蛋白": ["protein"], "蛋白质": ["protein"], "变异": ["variant", "mutation"], "突变": ["mutation", "variant"],
    "致病": ["pathogenic"], "热点": ["hotspot", "mutation"], "结构域": ["domain"], "结构": ["structure", "structural"],
    "通路": ["pathway"], "文献": ["literature", "pubmed", "paper"], "论文": ["paper", "pubmed"], "综述": ["review"],
    "临床": ["clinical"], "试验": ["trial", "clinical"], "药物": ["drug"], "靶点": ["target"], "成药性": ["druggability", "tractability", "target"],
    "抑制剂": ["inhibitor"], "化合物": ["compound"], "活性": ["activity", "potency"], "亲和力": ["affinity", "binding"], "结合": ["binding"],
    "表达": ["expression"], "差异": ["differential"], "差异表达": ["differential", "expression"], "单细胞": ["single-cell", "single cell", "scrna"],
    "细胞类型": ["cell type"], "细胞": ["cell"], "注释": ["annotation"], "组织": ["tissue"], "转录": ["transcription", "transcript"],
    "功能": ["function", "functional"], "约束": ["constraint"], "疾病": ["disease"], "数据集": ["dataset"], "相互作用": ["interaction"],
    "互作": ["interaction"], "序列": ["sequence"], "测序": ["sequencing"], "比对": ["alignment"], "组装": ["assembly"],
    "甲基化": ["methylation"], "染色质": ["chromatin"], "富集": ["enrichment"], "网络": ["network"], "免疫": ["immune"],
    "代谢": ["metabolic", "metabolism"], "微生物": ["microbial", "microbiome"], "进化": ["evolution", "phylogenetic"],
    "对接": ["docking"], "分子动力学": ["molecular dynamics"], "预后": ["prognosis", "survival"], "生存": ["survival"],
    "人群": ["population"], "遗传": ["genetic", "genetics"], "图谱": ["atlas"], "剪接": ["splicing"], "调控": ["regulation", "regulatory"],
    "信号": ["signaling"], "激酶": ["kinase"], "受体": ["receptor"], "抗体": ["antibody"], "载体": ["vector"], "编辑": ["editing"],
}
_WORD = re.compile(r"[a-z0-9][a-z0-9_\-]{2,}|[一-鿿]{2,}")
_STOP = {
    "the", "and", "for", "with", "from", "that", "this", "are", "use", "using", "data", "tool", "tools", "function", "functions",
    "can", "you", "all", "any", "not", "one", "its", "into", "via", "such", "each", "more", "than", "etc", "what", "which", "how",
}


def _tokens(text: str) -> set[str]:
    out: set[str] = set()
    for w in _WORD.findall(str(text or "").lower()):
        out.add(w)
        if re.fullmatch(r"[一-鿿]+", w) and len(w) > 2:  # Chinese has no spaces: its character pairs count as words too
            out.update(w[i:i + 2] for i in range(len(w) - 1))
    return out - _STOP


def _name_desc(item: Any) -> tuple[str, str]:
    if isinstance(item, dict):
        return str(item.get("name", "")), str(item.get("description", ""))
    return str(item), ""


def query_tokens(text: str) -> set[str]:
    """The words of a question, with the English words its Chinese terms stand for. The longest term wins: 结构域 (domain) does not also
    count as 结构 (structure)."""
    q = _tokens(text)
    rest = str(text or "")
    for cn in sorted(_CN_EN, key=len, reverse=True):
        if cn in rest:
            for w in _CN_EN[cn]:
                q |= _tokens(w)
            rest = rest.replace(cn, " ")
    return q


def prefilter(query: str, tools: list[dict[str, Any]], top_k: int = TOP_K) -> list[dict[str, Any]]:
    """The tools that best share words with the query, topped up to top_k from the rest of the list (the common ones first)."""
    q = query_tokens(query)
    if not q:
        return tools
    scored: list[tuple[int, dict[str, Any]]] = []
    for t in tools:
        name, desc = _name_desc(t)
        name_words = _tokens(name.replace("_", " "))
        desc_words = _tokens(desc)
        score = 3 * len(q & name_words) + len(q & desc_words)
        if score:
            scored.append((score, t))
    if not scored:
        return tools
    scored.sort(key=lambda x: -x[0])
    picked = [t for _, t in scored[:top_k]]
    names = {_name_desc(t)[0] for t in picked}
    for common in (True, False):  # room left: the common tools first, then the rest in the registry's own order
        for t in tools:
            if len(picked) >= top_k:
                return picked
            name, desc = _name_desc(t)
            if name in names:
                continue
            if common and "PREFERRED" not in desc:
                continue
            picked.append(t)
            names.add(name)
    return picked


def attach(agent: Any, top_k: int = TOP_K) -> None:
    """Narrow the tools the agent's retriever is given. Idempotent."""
    retriever = getattr(agent, "retriever", None)
    if retriever is None or getattr(retriever, "_prefilter_attached", False):
        return
    original = retriever.prompt_based_retrieval

    def narrowed(query: str, resources: dict, llm: Any = None) -> dict:
        res = dict(resources)
        if isinstance(res.get("tools"), list):
            res["tools"] = prefilter(query, res["tools"], top_k)
        if isinstance(res.get("libraries"), list):
            res["libraries"] = prefilter(query, res["libraries"], TOP_LIBRARIES)
        return original(query, res, llm=llm)

    retriever.prompt_based_retrieval = narrowed
    retriever._prefilter_attached = True
