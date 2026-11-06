"""The full dataset catalogue, added to the official A1 agent's system prompt from the outside.

The official A1 lists only the datasets already on disk, so it does not know the others exist. Biomni-Desk keeps the whole catalogue (the
datasets hosted on Zenodo) in the prompt as names and status only, to keep the prompt short. A description is one call away:
dataset_info(name) in the agent's Python. A dataset is fetched when a task needs it, with biomni.tool.support_tools.download_data_lake_file.
The agent class itself is not changed: its prompt generator is wrapped on the instance, and dataset_info is added to its Python environment.
"""

from __future__ import annotations

import builtins
import os
from typing import Any

ZENODO_URL = "https://zenodo.org/records/18759554/files"


def _local_names(data_lake_dir: str) -> set[str]:
    try:
        return set(os.listdir(data_lake_dir))
    except OSError:
        return set()


def catalog_block(datasets: dict[str, str], data_lake_dir: str, local: set[str] | None = None) -> str:
    """The catalogue as prompt text: one line per dataset with its status, and how to get a description or a dataset."""
    present = _local_names(data_lake_dir) if local is None else local
    lines = [
        "## Dataset catalogue (Biomni-Desk)",
        f"The datasets below are hosted at {ZENODO_URL}/<filename>. Each name ends with its status: 'available locally' or 'download needed'.",
        "For what a dataset contains, run dataset_info('<name>') in Python.",
        "To use a dataset whose status is 'download needed', fetch it first (it is cached, so a second call returns at once):",
        "```python",
        "from biomni.tool.support_tools import download_data_lake_file",
        f"path = download_data_lake_file('<filename>', '{data_lake_dir}')",
        "```",
        "Before you say that a file is available locally, check it with os.path.exists on its path; do not decide it from memory or from a web page.",
        "",
    ]
    for name in sorted(datasets):
        status = "available locally" if name in present else "download needed"
        lines.append(f"- {name} [{status}]")
    return "\n".join(lines)


def _describer(agent: Any):
    def dataset_info(name: str) -> str:
        """What a dataset of the catalogue contains (one line), and whether it is on disk."""
        datasets = dict(getattr(agent, "data_lake_dict", {}) or {})
        key = str(name or "").strip()
        if key not in datasets:
            close = [k for k in datasets if key.lower() in k.lower()][:5]
            return f"Not in the catalogue: {key!r}." + (f" Close names: {', '.join(close)}" if close else "")
        data_lake_dir = os.path.join(str(getattr(agent, "path", "") or ""), "data_lake")
        state = "available locally" if os.path.exists(os.path.join(data_lake_dir, key)) else "download needed"
        desc = " ".join(str(datasets[key] or "").split())
        return f"{key}: {desc} [{state}]"

    return dataset_info


def attach(agent: Any) -> None:
    """Wrap the agent's prompt generator so every prompt it builds (at start-up and per task) carries the catalogue, and make
    dataset_info available in its Python environment.

    Idempotent: attaching twice does not stack the catalogue twice.
    """
    if getattr(agent, "_catalog_attached", False):
        return
    original = agent._generate_system_prompt

    def with_catalog(*args: Any, **kwargs: Any) -> str:
        prompt = original(*args, **kwargs)
        data_lake_dir = os.path.join(str(getattr(agent, "path", "") or ""), "data_lake")
        datasets = dict(getattr(agent, "data_lake_dict", {}) or {})
        if not datasets:
            return prompt
        return prompt + "\n\n" + catalog_block(datasets, data_lake_dir)

    describe = _describer(agent)
    if not hasattr(agent, "_custom_functions"):
        agent._custom_functions = {}
    agent._custom_functions["dataset_info"] = describe
    if not hasattr(builtins, "_biomni_custom_functions"):
        builtins._biomni_custom_functions = {}
    builtins._biomni_custom_functions["dataset_info"] = describe

    agent._generate_system_prompt = with_catalog
    agent._catalog_attached = True
