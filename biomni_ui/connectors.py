"""Which research databases the agent may query: one switch per database family, as Claude Science has per connector.

A switched-off database is hidden from the model's tool list, refused when a tool is called by name, and refused when a database function
is called from Python (each module that defines one calls guard() at its end, so every importer gets the checked version). The switch is a
file in ui_data, read on each call: a change needs no restart, and the Python tool (another process) sees it too.
"""

from __future__ import annotations

import functools
import json
import os
import threading
from pathlib import Path
from typing import Any, Callable

# Titles are English; the web interface translates them for display.
GROUPS: tuple[dict[str, Any], ...] = (
    {"id": "gnomad", "title": "gnomAD gene constraint", "tools": ("gnomad_constraint",)},
    {"id": "clinicaltrials", "title": "ClinicalTrials.gov trials", "tools": ("clinical_trials", "clinical_lookup")},
    {"id": "openfda", "title": "openFDA adverse events and labels", "tools": ("fda_adverse_events",)},
    {"id": "chembl", "title": "ChEMBL compound activity", "tools": ("chembl_target_compounds",)},
    {"id": "opentargets", "title": "Open Targets associations and druggability", "tools": ("open_targets", "target_tractability")},
    {"id": "uniprot", "title": "UniProt proteins", "tools": ("uniprot_lookup",)},
    {"id": "gtex", "title": "GTEx tissue expression", "tools": ("gtex_expression",)},
    {"id": "geo", "title": "GEO dataset search", "tools": ("geo_search",)},
    {"id": "string", "title": "STRING protein interactions", "tools": ("string_interactions",)},
    {"id": "reactome", "title": "Reactome pathways", "tools": ("reactome_pathways",)},
    {"id": "literature", "title": "PubMed and Europe PMC literature", "tools": ("pubmed_search", "europepmc_search", "paper_abstracts")},
    {"id": "civic", "title": "CIViC tumour variants", "tools": ("civic_gene_variants",)},
)
STORE = Path(__file__).resolve().parent.parent / "ui_data" / "connectors.json"
_lock = threading.Lock()
_group_of = {tool: g["id"] for g in GROUPS for tool in g["tools"]}
_title = {g["id"]: g["title"] for g in GROUPS}


def group_of(tool: str) -> str | None:
    """The English title of the database connector that a tool belongs to, or None for tools that are not database calls."""
    gid = _group_of.get(tool)
    return _title.get(gid) if gid else None


def _disabled() -> set[str]:
    """The ids of the connectors that are switched off, read from the store file (empty when there is none)."""
    try:
        data = json.loads(STORE.read_text(encoding="utf-8"))
        return {str(x) for x in data.get("disabled", []) if str(x) in _title}
    except (OSError, ValueError, AttributeError):
        return set()


def enabled(tool: str) -> bool:
    """A tool that belongs to no connector (the biomni functions, the web search) is always on."""
    group = _group_of.get(tool)
    return group is None or group not in _disabled()


def off_message(tool: str) -> str:
    """What a switched-off tool returns instead of querying the database."""
    title = _title.get(_group_of.get(tool, ""), tool)
    return f"The database connector “{title}” is switched off in Settings, so it was not queried this time. Switch it on there when needed."


def refusal_message(title: str) -> str:
    """What a database call returns when the user did not allow it for this request."""
    return f"The database “{title}” was not queried: the user did not allow it for this request. Carry on without it, or say what is missing."


def listing() -> list[dict[str, Any]]:
    off = _disabled()
    return [{"id": g["id"], "title": g["title"], "tools": list(g["tools"]), "enabled": g["id"] not in off} for g in GROUPS]


def set_enabled(group_id: str, on: bool) -> bool:
    """Switch one connector on or off. False when there is no such connector."""
    if group_id not in _title:
        return False
    with _lock:
        off = _disabled()
        (off.discard if on else off.add)(group_id)
        STORE.parent.mkdir(parents=True, exist_ok=True)
        tmp = STORE.with_suffix(".tmp")
        tmp.write_text(json.dumps({"disabled": sorted(off)}, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(STORE)
    return True


def _guarded(name: str, fn: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap one database function so it checks the switch on every call."""

    @functools.wraps(fn)
    def inner(*args: Any, **kwargs: Any) -> Any:
        if not enabled(name):
            return off_message(name)
        session = os.environ.get("BIOMNI_KERNEL_SESSION")
        group = group_of(name)
        if session is not None and group:  # inside a Python session: the task that owns it decides (see permissions.py)
            from biomni_ui import permissions

            if not session or not permissions.kernel_check(name, group, session):
                return refusal_message(group)
        return fn(*args, **kwargs)

    inner._connector_guarded = True  # type: ignore[attr-defined]
    return inner


def guard(namespace: dict[str, Any]) -> None:
    """Wrap the database functions defined in a module (its globals) so the switch is checked on every call. Idempotent."""
    for tool in _group_of:
        fn = namespace.get(tool)
        if callable(fn) and not getattr(fn, "_connector_guarded", False):
            namespace[tool] = _guarded(tool, fn)
