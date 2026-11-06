"""FastAPI backend for the new web UI.

    .venv\\Scripts\\python.exe -m biomni_ui.server        # http://127.0.0.1:8765

Endpoints
    GET    /api/health
    GET    /api/conversations                 list, newest first
    GET    /api/conversations/{id}            full history with every event
    PATCH  /api/conversations/{id}            {"title": "..."}
    DELETE /api/conversations/{id}
    POST   /api/tasks                         {"prompt": "...", "conversation_id": optional} -> ids
    GET    /api/tasks/{id}/events             text/event-stream, resumable with ?from=<seq> or Last-Event-ID
    POST   /api/tasks/{id}/cancel
    POST   /api/tasks/{id}/review             independent second-opinion review (stored as an event)
    POST   /api/tasks/{id}/suggest            follow-up question suggestions (stored as an event)
    GET    /api/files?p=<absolute path>       a file the agent produced (restricted to the workspace)
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
# Must run before `biomni` is imported: BiomniConfig reads the environment at import time.
load_dotenv(ROOT / ".env", override=True)
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
# Agent code runs in worker threads; a GUI matplotlib backend (Tk) crashes the whole process there.
os.environ.setdefault("MPLBACKEND", "Agg")

from biomni_ui.compat import patch_httpx  # noqa: E402

patch_httpx()  # libraries that still pass httpx `proxies=` (e.g. scholarly) must not crash the tools

import uvicorn  # noqa: E402
from fastapi import FastAPI, File, Header, HTTPException, Query, Request, UploadFile  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse, StreamingResponse  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from biomni_ui import agent_catalog, agent_retrieval  # noqa: E402
from biomni_ui import assist, fast_tools, provider_profiles, research, tool_health, providers as ui_providers, catalog as ui_catalog, chatgpt_api, files, llm_calls, llm_guard, mentions, prefs as ui_prefs  # noqa: E402
from biomni_ui.codex_llm import ChatCodex, resolve_effort, resolve_model  # noqa: E402
from biomni_ui.models import DEFAULT_EFFORT, EFFORTS, ModelStore, cost_of  # noqa: E402
from biomni_ui import effort as effort_levels  # noqa: E402
from biomni_ui import environment  # noqa: E402
from biomni_ui.refs import RefResolver  # noqa: E402
from biomni_ui import settings as ui_settings  # noqa: E402
from biomni_ui.runner import Busy, Manager  # noqa: E402
from biomni_ui.skills import FIELDS, SkillStore  # noqa: E402
from biomni_ui import schedules, skill_import, agents, workdir  # noqa: E402
from biomni_ui.store import Store  # noqa: E402

HOST = os.getenv("BIOMNI_API_HOST", "127.0.0.1")
PORT = int(os.getenv("BIOMNI_API_PORT", "8765"))
# Any port on this machine's own loopback names may call the API (the web page is served from 3001 by default).
WEB_ORIGIN_REGEX = r"^http://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$"


SETTINGS_FILE = ROOT / "ui_data" / "settings.json"
store = Store(ROOT / "ui_data" / "biomni_ui.db")
skills = SkillStore(ROOT / "skills", ROOT / "ui_data" / "skills_state.json")
schedule_store = schedules.ScheduleStore(ROOT / "ui_data" / "schedules.json")
schedule_stop = threading.Event()
agent_store = agents.AgentStore(ROOT / "ui_data" / "agents.json")


def _make_agent():
    from biomni.agent import A1

    # The official A1 downloads the whole data lake from S3 at start-up unless it is told not to: Biomni-Desk fetches each dataset
    # from Zenodo when the agent asks for it, so start-up passes an empty list.
    agent = A1(expected_data_lake_files=[])
    agent_catalog.attach(agent)  # the full dataset catalogue joins the official prompt (the agent class itself is unchanged)
    agent_retrieval.attach(agent)  # the tool-selection step sees the best matches, not the whole registry
    agent.llm = _build_llm(search=True)  # our own model object: reasoning effort + client-side stop guard, upstream untouched
    research.bind(_build_llm, lambda: _build_llm(effort="medium") if (_active_entry() or {}).get("source") == "Codex" else _build_llm())
    fast_tools.route_tool_llm(lambda: _build_llm(effort="medium") if (_active_entry() or {}).get("source") == "Codex" else _build_llm())
    skills.sync_agent(agent)
    try:
        fast_tools.register(agent)
    except Exception as e:  # the stock tools still work; say so instead of failing to start
        print(f"fast literature tools not registered: {type(e).__name__}: {e}")
    return agent


manager = Manager(_make_agent, store)
manager.skill_store = skills
manager.llm_for_profile = lambda profile: _build_llm(entry=models.get(profile["model_id"]) if profile.get("model_id") else None, effort=profile.get("effort"), search=True)  # an agent profile's own model and effort
def _role_entry(key: str) -> dict | None:
    """The saved model chosen for one role in Settings (None: the main model)."""
    rid = ui_settings.load(SETTINGS_FILE).get(key)
    return models.get(rid) if rid else None


def _subagent_llm():
    """The model and reasoning level the sub-agents run on: the model Settings chooses (or the main model), at the sub-agent level
    (medium unless Settings sets another; sub-tasks are shorter, so a lower level keeps them quick)."""
    eff = ui_settings.load(SETTINGS_FILE).get("subagent_effort") or "medium"
    entry = _role_entry("subagent_model_id")
    return _build_llm(entry=entry, effort=eff, search=True)


def _planner_llm():
    """The model that drafts plans, when Settings chooses one (or a level for it); otherwise the main model."""
    eff = ui_settings.load(SETTINGS_FILE).get("planner_effort")
    entry = _role_entry("planner_model_id")
    if entry is None and not eff:
        return _llm()
    return _build_llm(entry=entry, effort=eff, search=False)


def _image_target():
    """(base URL, key, model) of the image model when Settings sets one. ChatGPT models are not used for pictures here."""
    entry = _role_entry("image_model_id")
    if not entry or entry.get("source") == "Codex":
        return None
    creds = providers.credentials(entry["provider"])
    if creds is None:
        return None
    base, key = creds
    return base, key, entry["model"]


def _role_settings() -> dict:
    """Settings the agent loop reads on each task: the sub-agent level, how many sub-agents run at once, and the memory switches.
    Defaults apply when a value is unset."""
    s = ui_settings.load(SETTINGS_FILE)
    out = {"subagent_effort": s.get("subagent_effort") or None}
    out.update({k: s.get(k, v) for k, v in ui_settings.DEFAULTS.items()})
    return out


manager.subagent_llm = _subagent_llm
manager.image_target = _image_target
manager.role_settings = _role_settings
manager.write_llm_factory = lambda: _build_llm(effort="medium" if _effort() in ("high", "xhigh") else _effort()) if (_active_entry() or {}).get("source") == "Codex" else None
manager.fast_llm_factory = lambda: _build_llm(effort="medium") if (_active_entry() or {}).get("source") == "Codex" else None
providers = ui_providers.ProviderStore(
    ROOT / "ui_data" / "providers.json",
    env_base_url=lambda: _config().base_url,
    env_api_key=lambda: _config().api_key,
)
models = ModelStore(ROOT / "ui_data" / "models.json", local_providers=providers.local_ids)
prefs_store = ui_prefs.PrefsStore(ROOT / "ui_data" / "prefs.json")
catalog = ui_catalog.Catalog()
resolver = RefResolver(ROOT / "ui_data" / "refs_cache.json")
STOPS = ["</execute>", "</solution>"]
NATIVE_SEARCH = os.getenv("BIOMNI_UI_NATIVE_SEARCH", "1") != "0"  # the agent's own model may search the web inside a reply


def _effort() -> str:
    return ui_settings.load(SETTINGS_FILE).get("reasoning_effort", DEFAULT_EFFORT)


def _active_entry() -> dict | None:
    """The model in use: the entry the settings point at (two providers can offer the same model name)."""
    cfg = _config()
    mid = ui_settings.load(SETTINGS_FILE).get("model_id")
    entry = models.get(mid) if mid else None
    return entry or models.find(cfg.source, cfg.llm)


def _is_openrouter(entry: dict | None) -> bool:
    p = providers.get(entry["provider"]) if entry and entry.get("source") == "Custom" else None
    return bool(p and "openrouter.ai" in p["base_url"])


def _profile_of(entry: dict | None) -> dict | None:
    """The documented thinking-level controls of this model's provider (None when it publishes none we know of)."""
    p = providers.get(entry["provider"]) if entry and entry.get("source") == "Custom" else None
    return provider_profiles.for_base_url(p["base_url"]) if p else None


def _model_effort(entry: dict | None, info: dict | None = None) -> tuple[list[str], str | None]:
    """(efforts this model accepts, the one in use). ChatGPT: the global setting. OpenRouter models: what OpenRouter
    says they support. Other providers publish no such list, so there is nothing we could honestly offer."""
    if entry is None:
        return [], None
    if entry["source"] == "Codex":
        return effort_levels.offered(list(EFFORTS)), effort_levels.floor(_effort())
    if not _is_openrouter(entry):
        prof = _profile_of(entry)
        if not prof:
            return [], None
        chosen = models.efforts().get(entry["id"])
        cur = chosen if chosen in prof["efforts"] else prof["default"]
        return effort_levels.offered(list(prof["efforts"])), effort_levels.floor(cur)
    info = info or catalog.peek(entry["model"])
    options = effort_levels.offered(list((info or {}).get("efforts") or []))
    if not options:
        return [], None
    chosen = models.efforts().get(entry["id"])
    picked = effort_levels.floor(chosen if chosen in options else (info or {}).get("default_effort") or options[0])
    return options, (picked if picked in options else options[0])


def _build_llm(source: str | None = None, model: str | None = None, effort: str | None = None, entry: dict | None = None, search: bool = False):
    """The chat model for a model entry (default: the one in use), talking to that entry's own provider."""
    cfg = _config()
    if entry is None:
        entry = models.find(source, model) if (source or model) else _active_entry()
    source = entry["source"] if entry else (source or cfg.source)
    model = entry["model"] if entry else (model or cfg.llm)
    if source == "Codex":
        eff = resolve_effort(effort or _effort())
        llm = ChatCodex(model=resolve_model(model), stop_sequences=STOPS, reasoning_effort=eff, native_search=search and NATIVE_SEARCH)
        return llm_guard.StopGuardLLM(llm, model=resolve_model(model), effort=eff)
    from biomni.llm import get_llm

    creds = providers.credentials(entry["provider"]) if entry else None
    if entry is not None and creds is None:
        p = providers.get(entry["provider"])
        raise RuntimeError(f"The provider “{p['name'] if p else entry['provider']}” has no usable API key yet. Add one under Settings → Models.")
    base_url, api_key = creds if creds else (cfg.base_url, cfg.api_key)
    llm = get_llm(model, stop_sequences=STOPS, source="Custom", base_url=base_url, api_key=api_key, config=cfg)
    eff = None
    info = catalog.get(model) if _is_openrouter(entry) else None
    options, current = _model_effort(entry, info)
    if options:
        eff = effort if effort in options else current
        if _is_openrouter(entry):
            llm.extra_body = {"reasoning": {"effort": eff}}  # OpenRouter's unified reasoning control
        else:
            llm.extra_body = provider_profiles.request_body(base_url, eff)  # the provider's own documented parameters
    return llm_guard.StopGuardLLM(llm, model=model, effort=eff)


def _warm() -> None:
    if setup_problem() is not None:
        return  # no usable model yet: do not try to build one; the page shows the setup message
    try:
        manager.agent()
    except Exception:
        pass  # the error is kept in manager.agent_error and shown by /api/health


def _config():
    from biomni.config import default_config

    return default_config


ui_settings.apply(_config(), ui_settings.load(SETTINGS_FILE))


@asynccontextmanager
async def lifespan(_app):
    # Build the agent in the background so the first task does not pay the start-up cost.
    catalog.warm()
    environment.start()  # what this machine can run, measured in the background
    threading.Thread(target=_warm, daemon=True, name="warm-up").start()
    workers = int(os.getenv("BIOMNI_UI_WORKERS", "3") or 0)
    if workers > 0 and not os.environ.get("BIOMNI_UI_WORKER"):
        manager.start_workers(workers, ROOT)
    threading.Thread(target=schedules.loop, args=(schedule_store, _start_scheduled, lambda: manager.agent_ready, schedule_stop), daemon=True, name="scheduler").start()
    yield
    schedule_stop.set()
    manager.stop_workers()


app = FastAPI(title="Biomni-Desk API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origin_regex=WEB_ORIGIN_REGEX, allow_methods=["*"], allow_headers=["*"])


class NewTask(BaseModel):
    prompt: str = Field(min_length=1, max_length=20000)
    conversation_id: str | None = None
    approval: Approval | None = None  # plan and clarification answers the user approved
    mentions: list[dict[str, str]] = Field(default_factory=list, max_length=10)
    project_id: str | None = Field(default=None, max_length=40)  # where a brand-new conversation belongs
    mode: str = Field(default="ask", pattern="^(plan|ask|auto)$")  # plan: approve the plan, then run; ask: run and ask when unsure; auto: run, no questions
    agent_id: str | None = Field(default=None, max_length=60)  # an agent profile; its mode, model, effort and tools apply to this task


class PlanRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=20000)
    conversation_id: str | None = None


class Approval(BaseModel):
    plan: list[str] = Field(default_factory=list, max_length=12)
    answers: list[tuple[str, str]] = Field(default_factory=list, max_length=3)


class ConversationPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=80)
    project_id: str | None = Field(default=None, max_length=40)


class ZipIn(BaseModel):
    paths: list[str] = Field(max_length=100)


class Rename(BaseModel):
    title: str = Field(min_length=1, max_length=80)


@app.get("/api/health")
def health():
    from biomni.config import default_config

    return {
        "ok": True,
        "setup": setup_problem(),
        "agent_ready": manager.agent_ready,
        "agent_error": manager.agent_error,
        "busy": manager.busy,
        "source": default_config.source,
        "model": default_config.llm,
        "tool_retriever": default_config.use_tool_retriever,
        "commercial_mode": default_config.commercial_mode,
    }


class SkillIn(BaseModel):
    id: str | None = None
    title: str = ""
    description: str = ""
    category: str = ""
    when_to_use: str = ""
    avoid: str = ""
    uses: str = ""
    chain: str = ""
    body: str = ""


class SettingsIn(BaseModel):
    source: str | None = None
    model: str | None = None
    use_tool_retriever: bool | None = None
    commercial_mode: bool | None = None


class Toggle(BaseModel):
    enabled: bool


def _resync_skills() -> None:
    if manager.agent_ready:
        skills.sync_agent(manager.agent())
    for slot in manager._procs:
        slot.command("sync_skills")


def _custom_ready() -> bool:
    """At least one provider can be used."""
    return providers.any_ready()


PLACEHOLDER_MARKERS = ("your_", "your-", "<", "xxx", "_here")


def _real_key(value: str | None) -> bool:
    """A key counts only when it is set and is not a template placeholder such as your_anthropic_api_key_here."""
    v = (value or "").strip()
    return bool(v) and not any(m in v.lower() for m in PLACEHOLDER_MARKERS)


def setup_problem() -> str | None:
    """Why no model can answer yet, in English for the page; None when a model is ready."""
    entry = _active_entry()
    if entry is not None:
        if entry.get("source") == "Codex":
            if chatgpt_api.is_logged_in() or shutil.which("codex"):
                return None
            return "ChatGPT is not logged in. Open Settings and choose Log in to ChatGPT."
        if providers.ready(entry["provider"]):
            return None
        return "The selected model's provider has no API key yet. Open Settings, then Models, to add one."
    cfg = _config()
    llm_name = str(cfg.llm or "")
    source = cfg.source or ("Anthropic" if llm_name.startswith("claude-") else "OpenAI" if llm_name.startswith("gpt-") else None)
    env_name = {"Anthropic": "ANTHROPIC_API_KEY", "OpenAI": "OPENAI_API_KEY"}.get(source or "")
    if env_name and _real_key(os.getenv(env_name)):
        return None
    return "No model is set up yet. Open Settings, then Models, to log in to ChatGPT or add an API key (for example OpenRouter)."


def _models_view() -> dict:
    cfg = _config()
    active = _active_entry()
    names = {p["id"]: p["name"] for p in providers.list()}
    rows = []
    for m in models.list():
        orouter = _is_openrouter(m)
        info = catalog.peek(m["model"]) if orouter else None
        options, current = _model_effort(m, info)
        rows.append({
            **m,
            "provider_name": names.get(m["provider"], m["provider"]) if m["source"] == "Custom" else "ChatGPT",
            "provider_ready": m["source"] == "Codex" or providers.ready(m["provider"]),
            "effort_options": options,
            "effort": current,
            # None = not checked (only OpenRouter publishes a list we can check against); False = no longer there
            "available": (None if not catalog.peek_ready() else info is not None) if orouter else None,
            "price": {"prompt": info["prompt_per_m"], "completion": info["completion_per_m"], "context": info["context"]} if info else None,
        })
    active_row = next((r for r in rows if active and r["id"] == active["id"]), None)
    return {
        "models": rows,
        "removed": len(models.removed()),
        "active": {
            "id": active["id"] if active else None,
            "source": cfg.source,
            "model": cfg.llm,
            "reasoning_effort": (active_row or {}).get("effort") or _effort(),
            "effort_options": (active_row or {}).get("effort_options", []),
        },
        "custom_ready": _custom_ready(),
        "efforts": effort_levels.offered(list(EFFORTS)),
        "providers": providers.list(),
        "roles": _model_roles(),
    }


def _model_roles() -> dict:
    """Which model does each helper role (None means the main model), the reasoning level for the planner, sub-agents and reviewer,
    how many sub-agents run at once, and the memory switches."""
    saved = ui_settings.load(SETTINGS_FILE)
    out: dict = {k: saved.get(k) or None for k in (*ui_settings.ROLE_KEYS, *ui_settings.ROLE_EFFORT_KEYS)}
    out.update({k: saved.get(k, v) for k, v in ui_settings.DEFAULTS.items()})
    return out


class RolesIn(BaseModel):
    """Only the fields sent are changed; a field sent as null clears a model or level back to the main model's."""
    planner_model_id: str | None = Field(default=None, max_length=120)
    subagent_model_id: str | None = Field(default=None, max_length=120)
    reviewer_model_id: str | None = Field(default=None, max_length=120)
    image_model_id: str | None = Field(default=None, max_length=120)
    planner_effort: str | None = Field(default=None, max_length=20)
    subagent_effort: str | None = Field(default=None, max_length=20)
    reviewer_effort: str | None = Field(default=None, max_length=20)
    subagent_max: int | None = None
    memory_recall_chars: int | None = None
    memory_auto: bool | None = None


@app.put("/api/model-roles")
def set_model_roles(body: RolesIn):
    try:
        changes = ui_settings.validate_roles(body.model_dump(exclude_unset=True), {m["id"] for m in models.list()}, set(effort_levels.ORDER))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    ui_settings.save(SETTINGS_FILE, ui_settings.load(SETTINGS_FILE), changes)
    return _models_view()


def _settings_view() -> dict:
    cfg = _config()
    return {
        "values": {
            "source": cfg.source,
            "model": cfg.llm,
            "use_tool_retriever": cfg.use_tool_retriever,
            "commercial_mode": cfg.commercial_mode,
            "reasoning_effort": _effort(),
        },
        "sources": ui_settings.SOURCES,
        "custom_ready": _custom_ready(),
    }


@app.get("/api/settings")
def get_settings():
    return _settings_view()


@app.put("/api/settings")
def put_settings(body: SettingsIn):
    """Retriever / commercial-mode changes rebuild the agent; model changes use /api/active (instant)."""
    if manager.busy:
        raise HTTPException(status_code=409, detail="A task is already running. Wait for it to finish or stop it.")
    cfg = _config()
    changes = {k: v for k, v in body.model_dump(exclude_none=True).items() if k in ("use_tool_retriever", "commercial_mode")}
    try:
        clean = ui_settings.validate(changes, custom_ready=_custom_ready())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    rebuild = any(getattr(cfg, k) != v for k, v in clean.items())
    ui_settings.save(SETTINGS_FILE, ui_settings.load(SETTINGS_FILE), clean)
    ui_settings.apply(cfg, clean)
    if rebuild:
        manager.reset_agent()  # these two are read when the agent is built
        threading.Thread(target=_warm, daemon=True, name="warm-up").start()
    return _settings_view()


class ActiveIn(BaseModel):
    id: str | None = None
    reasoning_effort: str | None = None
    confirm_paid: bool = False  # the user explicitly accepted that this model is billed per use


class ModelIn(BaseModel):
    model: str
    label: str = ""
    note: str = ""
    provider: str = "openrouter"


@app.get("/api/models")
def list_models():
    return _models_view()


def _provider_problem(entry: dict) -> str | None:
    """Why a model cannot be used right now (None: fine)."""
    if entry["source"] != "Custom" or providers.ready(entry["provider"]):
        return None
    p = providers.get(entry["provider"])
    return f"The provider “{p['name'] if p else entry['provider']}” has no usable API key yet. Add one under Settings → Models."


@app.put("/api/active")
def set_active(body: ActiveIn):
    """Switch the live model (and/or its reasoning effort) without rebuilding the agent: takes effect immediately."""
    if manager.busy:
        raise HTTPException(status_code=409, detail="A task is already running. Wait for it to finish or stop it.")
    cfg = _config()
    target = models.get(body.id) if body.id else _active_entry()
    if body.id:
        if target is None:
            raise HTTPException(status_code=404, detail="This model does not exist")
        problem = _provider_problem(target)
        if problem:
            raise HTTPException(status_code=400, detail=problem)
        if target["cost"] == "paid" and not body.confirm_paid:
            raise HTTPException(status_code=409, detail=f"“{target['label']}” is a paid model billed per use. Confirm before you use it.")
        if _is_openrouter(target) and catalog.available() and catalog.get(target["model"]) is None:
            raise HTTPException(status_code=400, detail=f"“{target['label']}” is no longer listed on OpenRouter (it may have been retired), so it cannot be used. You can delete it.")
    changes: dict = {}
    if body.id and target:
        changes.update(source=target["source"], model=target["model"], model_id=target["id"])
    effort_for_build = None
    if body.reasoning_effort is not None:
        if target is None:
            raise HTTPException(status_code=400, detail="No model here can adjust reasoning effort")
        effort_for_build = _validated_effort(target, body.reasoning_effort, changes)
    if not changes and effort_for_build is None:
        return _models_view()
    try:
        new_llm = _build_llm(entry=target, effort=effort_for_build, search=True)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"This model cannot be used: {type(e).__name__}: {e}") from e
    if changes:
        ui_settings.save(SETTINGS_FILE, ui_settings.load(SETTINGS_FILE), changes)
        ui_settings.apply(cfg, {k: v for k, v in changes.items() if k in ("source", "model")})
    if manager.agent_ready:
        manager.agent().llm = new_llm  # the agent reads self.llm on every call
    return _models_view()


def _validated_effort(entry: dict, wanted: str, changes: dict | None = None) -> str:
    """Check `wanted` against what this model supports and remember it. For ChatGPT the global setting is changed."""
    if entry["source"] == "Codex":
        try:
            effort = resolve_effort(wanted)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        if changes is not None:
            changes["reasoning_effort"] = effort
        else:
            ui_settings.save(SETTINGS_FILE, ui_settings.load(SETTINGS_FILE), {"reasoning_effort": effort})
        return effort
    if _is_openrouter(entry):
        options = effort_levels.offered((catalog.get(entry["model"]) or {}).get("efforts") or [])
    else:
        options = effort_levels.offered(list((_profile_of(entry) or {}).get("efforts") or []))
    if wanted not in options:
        raise HTTPException(status_code=400, detail=f"This model does not support “{wanted}”. It supports: {', '.join(options) or '(reasoning effort cannot be adjusted)'}")
    models.set_effort(entry["id"], wanted)
    return wanted


class EffortIn(BaseModel):
    effort: str


@app.put("/api/models/{model_id}/effort")
def set_model_effort(model_id: str, body: EffortIn):
    """Set one model's reasoning effort. It never switches the model, so it can never start a paid one by accident."""
    if manager.busy:
        raise HTTPException(status_code=409, detail="A task is already running. Wait for it to finish or stop it.")
    entry = models.get(model_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="This model does not exist")
    effort = _validated_effort(entry, body.effort)
    active = _active_entry()
    if active and active["id"] == entry["id"] and manager.agent_ready:
        manager.agent().llm = _build_llm(entry=entry, effort=effort, search=True)  # the very next model call uses it
    return _models_view()


@app.get("/api/catalog")
def model_catalog(q: str = Query("", max_length=80), free: bool = False, limit: int = Query(30, ge=1, le=100)):
    """Models that really exist on OpenRouter right now (searchable), with price, context size and supported efforts."""
    rows = catalog.search(q, free_only=free, limit=limit)
    if rows is None:
        return {"available": False, "results": [], "have": []}
    return {"available": True, "results": rows, "have": [m["model"] for m in models.list()]}


# ---- providers (any OpenAI-compatible endpoint) -----------------------------------------------------------------
_provider_models: dict[str, tuple[float, list[str]]] = {}


def _ids_of(provider_id: str, refresh: bool = False) -> list[str]:
    """The model ids a provider lists, cached for five minutes. Raises RuntimeError with a readable reason."""
    import time

    hit = _provider_models.get(provider_id)
    if hit and not refresh and time.time() - hit[0] < 300:
        return hit[1]
    p = providers.get(provider_id)
    creds = providers.credentials(provider_id)
    if p is None or creds is None:
        raise RuntimeError("This provider has no usable API key yet")
    ids = [i for i in ui_providers.fetch_model_ids(creds[0], creds[1] if not p["local"] else None) if not ui_catalog.GPT_RE.search(i)]
    _provider_models[provider_id] = (time.time(), ids)
    return ids


class ProviderIn(BaseModel):
    name: str = Field(default="", max_length=40)
    base_url: str = Field(default="", max_length=300)
    api_key: str = Field(default="", max_length=500)
    preset: str | None = None


@app.get("/api/providers")
def list_providers():
    return {"providers": providers.list(), "presets": ui_providers.PRESETS}


@app.get("/api/call-counts")
def get_call_counts(kind: str = "tool", limit: int = 20):
    """How often the common ways were used: kind = tool | skill | func (counts only). (/api/usage is the model-usage page's endpoint.)"""
    from biomni_ui import usage

    if kind not in ("tool", "skill", "func"):
        raise HTTPException(status_code=400, detail="kind must be tool, skill or func")
    return {"kind": kind, "items": usage.store().top(kind, max(1, min(limit, 100)))}


@app.post("/api/providers")
def add_provider(body: ProviderIn):
    try:
        return providers.add(body.name, body.base_url, body.api_key, body.preset)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.patch("/api/providers/{provider_id}")
def update_provider(provider_id: str, body: ProviderIn):
    if provider_id == ui_providers.BUILTIN_ID:
        raise HTTPException(status_code=403, detail="This provider comes from .env. To change it, edit the .env file directly.")
    try:
        out = providers.update(provider_id, name=body.name or None, base_url=body.base_url or None, api_key=body.api_key)
    except KeyError:
        raise HTTPException(status_code=404, detail="This provider does not exist") from None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    _provider_models.pop(provider_id, None)
    return out


@app.delete("/api/providers/{provider_id}")
def delete_provider(provider_id: str):
    if provider_id == ui_providers.BUILTIN_ID:
        raise HTTPException(status_code=403, detail="This provider comes from .env and cannot be deleted here.")
    active = _active_entry()
    if active and active.get("provider") == provider_id:
        raise HTTPException(status_code=409, detail="A model from this provider is in use. Switch to another model first.")
    if not providers.delete(provider_id):
        raise HTTPException(status_code=404, detail="This provider does not exist")
    removed = models.delete_provider_models(provider_id)
    _provider_models.pop(provider_id, None)
    return {"ok": True, "models_removed": removed, **_models_view()}


@app.post("/api/providers/{provider_id}/test")
def test_provider(provider_id: str):
    """Ask the provider for its model list: proves the address is right and the key is accepted."""
    import time

    t0 = time.time()
    try:
        ids = _ids_of(provider_id, refresh=True)
        return {"ok": True, "count": len(ids), "seconds": round(time.time() - t0, 1)}
    except RuntimeError as e:
        return {"ok": False, "error": str(e), "seconds": round(time.time() - t0, 1)}


@app.get("/api/providers/{provider_id}/models")
def provider_models(provider_id: str, q: str = Query("", max_length=80), free: bool = False, limit: int = Query(40, ge=1, le=200)):
    """Models a provider really offers, to pick from when adding one. Same result shape for every provider."""
    p = providers.get(provider_id)
    if p is None:
        raise HTTPException(status_code=404, detail="This provider does not exist")
    have = [m["model"] for m in models.list() if m.get("provider") == provider_id]
    if _is_openrouter({"source": "Custom", "provider": provider_id}):
        rows = catalog.search(q, free_only=free, limit=limit)
        if rows is None:
            return {"available": False, "error": "Cannot reach OpenRouter, so the model list cannot be fetched.", "results": [], "have": have, "rich": True}
        return {"available": True, "results": rows, "have": have, "rich": True}
    try:
        ids = _ids_of(provider_id)
    except RuntimeError as e:
        return {"available": False, "error": str(e), "results": [], "have": have, "rich": False}
    words = q.lower().split()
    rows = [{"id": i, "name": i, "free": False, "prompt_per_m": None, "completion_per_m": None, "context": None, "efforts": [], "default_effort": None}
            for i in ids if all(w in i.lower() for w in words)]
    return {"available": True, "results": rows[:limit], "total": len(rows), "have": have, "rich": False}


@app.post("/api/models")
def add_model(body: ModelIn):
    name = body.model.strip()
    p = providers.get(body.provider)
    if p is None:
        raise HTTPException(status_code=404, detail="This provider does not exist")
    info = None
    if _is_openrouter({"source": "Custom", "provider": body.provider}):
        info = catalog.get(name)
        if catalog.available() and info is None:
            raise HTTPException(status_code=400, detail="This model is not on OpenRouter (the name may be wrong, or it has been retired). Search above for one that exists.")
    else:
        try:
            ids = _ids_of(body.provider)
        except RuntimeError as e:
            raise HTTPException(status_code=400, detail=f"Cannot confirm that this model exists: {e}") from e
        if name not in ids:
            raise HTTPException(status_code=400, detail=f"“{p['name']}” has no model named {name} in its list. Search for one that exists.")
    try:
        entry = models.add(name, body.label or (info or {}).get("name", ""), body.note, body.provider)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    full = models.get(entry["id"]) or entry
    return {"added": {**entry, "cost": full.get("cost", "paid")}, "verified": True, **_models_view()}


@app.delete("/api/models/{model_id}")
def delete_model(model_id: str):
    entry = models.get(model_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="This model does not exist")
    if entry["source"] == "Codex":
        raise HTTPException(status_code=403, detail="ChatGPT is the main model and cannot be deleted (if you do not want to see it, just do not use it)")
    active = _active_entry()
    if active and active["id"] == entry["id"]:
        raise HTTPException(status_code=409, detail="This model is in use. Switch to another model first.")
    models.delete(model_id)
    return _models_view()


@app.post("/api/models/restore")
def restore_models():
    """Bring back the built-in models that were deleted."""
    return {"restored": models.restore_defaults(), **_models_view()}


@app.post("/api/models/{model_id}/test")
def test_model(model_id: str, confirm_paid: bool = False):
    """One tiny call to check the model answers; does not change the live model."""
    import time

    entry = models.get(model_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="This model does not exist")
    problem = _provider_problem(entry)
    if problem:
        raise HTTPException(status_code=400, detail=problem)
    if entry["cost"] == "paid" and not confirm_paid:
        raise HTTPException(status_code=409, detail=f"“{entry['label']}” is a paid model. A test call is billed too, so confirm first.")
    t0 = time.time()
    try:
        reply = _build_llm(entry=entry).invoke([("human", "Reply with the single word: ok")])
        text = reply.content if isinstance(reply.content, str) else str(reply.content)
        return {"ok": True, "seconds": round(time.time() - t0, 1), "reply": text.strip()[:80]}
    except Exception as e:
        return {"ok": False, "seconds": round(time.time() - t0, 1), "error": f"{type(e).__name__}: {str(e)[:300]}"}


# ---- ChatGPT sign-in (device code), see chatgpt_api.py ------------------------------------------------------------
_login: dict = {"device": None, "error": None, "started": 0.0}
_login_lock = threading.Lock()


def _chatgpt_view() -> dict:
    with _login_lock:
        dev = _login["device"]
        pending = (
            {"user_code": dev["user_code"], "verification_url": dev["verification_url"]} if dev else None
        )
        return {"logged_in": chatgpt_api.is_logged_in(), "pending": pending, "error": _login["error"]}


def _login_worker(device: dict) -> None:
    try:
        chatgpt_api.poll_device_code(device)
        err = None
    except Exception as e:  # noqa: BLE001 - shown to the user as is
        err = str(e)
    with _login_lock:
        if _login["device"] is device:
            _login["device"], _login["error"] = None, err


@app.get("/api/chatgpt")
def chatgpt_status():
    return _chatgpt_view()


@app.post("/api/chatgpt/login")
def chatgpt_login():
    """Start the device-code sign-in; the user types the returned code at the returned address."""
    try:
        device = chatgpt_api.request_device_code()
    except chatgpt_api.ChatGPTAuthError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    with _login_lock:
        _login.update(device=device, error=None)
    threading.Thread(target=_login_worker, args=(device,), daemon=True, name="chatgpt-login").start()
    return _chatgpt_view()


@app.post("/api/chatgpt/logout")
def chatgpt_logout():
    chatgpt_api.logout()
    with _login_lock:
        _login.update(device=None, error=None)
    return _chatgpt_view()


@app.get("/api/skills")
def list_skills():
    return skills.list()


@app.get("/api/skills/{skill_id}")
def get_skill(skill_id: str):
    s = skills.get(skill_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    return s


def _save_skill(skill_id: str, body: SkillIn):
    try:
        s = skills.save(skill_id, {k: getattr(body, k) for k in FIELDS}, body.body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    _resync_skills()
    return s


@app.post("/api/skills")
def create_skill(body: SkillIn):
    if not body.id:
        raise HTTPException(status_code=400, detail="A skill ID is required")
    if skills.get(body.id):
        raise HTTPException(status_code=409, detail="This ID already exists")
    return _save_skill(body.id, body)


@app.put("/api/skills/{skill_id}")
def update_skill(skill_id: str, body: SkillIn):
    existing = skills.get(skill_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    if existing["source"] == "builtin":
        raise HTTPException(status_code=403, detail="Built-in skills cannot be edited. Copy one as your own skill, then edit the copy.")
    return _save_skill(skill_id, body)


@app.delete("/api/skills/{skill_id}")
def delete_skill(skill_id: str):
    existing = skills.get(skill_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    if existing["source"] == "builtin":
        raise HTTPException(status_code=403, detail="Built-in skills cannot be deleted, only turned off.")
    skills.delete(skill_id)
    from biomni_ui import github_skills

    github_skills.forget(skill_id)  # a deleted skill has no source left to check for updates
    _resync_skills()
    return {"ok": True}


@app.patch("/api/skills/{skill_id}")
def toggle_skill(skill_id: str, body: Toggle):
    if skills.get(skill_id) is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    skills.set_enabled(skill_id, body.enabled)
    _resync_skills()
    return {"ok": True}


@app.get("/api/conversations")
def list_conversations():
    return store.list_conversations()


@app.get("/api/conversations/{conv_id}")
def get_conversation(conv_id: str):
    conv = store.get_conversation(conv_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@app.patch("/api/conversations/{conv_id}")
def update_conversation(conv_id: str, body: ConversationPatch):
    """Rename it and/or move it to another project (the page calls this "Transfer")."""
    if body.title is not None and not store.rename(conv_id, body.title):
        raise HTTPException(status_code=404, detail="Conversation not found")
    if body.project_id is not None and not store.set_project(conv_id, body.project_id):
        raise HTTPException(status_code=404, detail="Conversation or project not found")
    return {"ok": True}


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)


@app.get("/api/projects")
def list_projects():
    return store.list_projects()


@app.post("/api/projects")
def create_project(body: ProjectIn):
    try:
        return store.create_project(body.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.patch("/api/projects/{project_id}")
def rename_project(project_id: str, body: ProjectIn):
    if not store.rename_project(project_id, body.name):
        raise HTTPException(status_code=404, detail="Project not found, or it is the default project (it cannot be renamed)")
    return store.list_projects()


@app.get("/api/projects/{project_id}/summary")
def project_summary(project_id: str):
    """What the project holds, for the project page and the delete confirmation."""
    from biomni_ui import notes

    if project_id != "quick" and not any(p["id"] == project_id for p in store.list_projects()):
        raise HTTPException(status_code=404, detail="Project not found")
    settings = store.get_project_settings(project_id)
    counts = store.project_summary(project_id)
    return {
        **counts,
        "notes": notes.count_for_project(project_id),
        "files": len(settings.get("files", [])),
        "skills": settings.get("skills", []),
        "tools_off": settings.get("tools_off", []),
        "memory_on": settings.get("memory_on", True),
    }


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str, mode: str = "keep"):
    """mode "keep" (the default) moves the project's sessions to the quick-task area; mode "cascade" deletes the sessions, their
    tasks, published records, the project's notes and its working folders as well."""
    import re as _re
    from biomni_ui import notes

    if mode not in ("keep", "cascade"):
        raise HTTPException(status_code=400, detail="mode must be keep or cascade")
    if mode == "keep":
        if not store.delete_project(project_id):
            raise HTTPException(status_code=404, detail="Project not found, or it is the default project (it cannot be deleted)")
        return store.list_projects()
    if project_id == "quick" or not any(p["id"] == project_id for p in store.list_projects()):
        raise HTTPException(status_code=404, detail="Project not found, or it is the default project (it cannot be deleted)")
    conv_ids = store.delete_project_cascade(project_id)
    notes.delete_project(project_id)
    base = workdir.results_base()
    for cid in conv_ids:
        folder = base / _re.sub(r"[^A-Za-z0-9_-]", "_", cid or "")
        if cid and folder.is_dir() and folder.parent == base:
            shutil.rmtree(folder, ignore_errors=True)
    return store.list_projects()


@app.get("/api/search")
def search_sessions(q: str = "", project: str | None = None):
    return {"results": store.search(q, project)}


# ---- versions, provenance and comments on result files ------------------------------------------

def _session_folder(cid: str) -> Path:
    if not cid or store.get_conversation(cid) is None:
        raise HTTPException(status_code=404, detail="No such session")
    return workdir.conversation_dir(cid)


def _in_session(folder: Path, path: str) -> str:
    """A result file's path as the version index keeps it: relative to the session folder (an absolute path inside it is accepted)."""
    p = Path(path)
    if not p.is_absolute():
        return p.as_posix()
    try:
        return p.resolve().relative_to(folder.resolve()).as_posix()
    except ValueError as e:
        raise HTTPException(status_code=400, detail="That file is not part of this session") from e


@app.get("/api/conversations/{cid}/files")
def versioned_files(cid: str):
    from biomni_ui import versions

    return {"files": list(versions.all_files(_session_folder(cid)).values())}


@app.get("/api/conversations/{cid}/versions")
def file_versions(cid: str, path: str):
    from biomni_ui import versions

    folder = _session_folder(cid)
    return {"versions": versions.versions_of(folder, _in_session(folder, path))}


@app.get("/api/conversations/{cid}/version-file")
def version_file(cid: str, sha: str, name: str = "file", download: bool = False):
    from biomni_ui import versions

    blob = versions.blob_path(_session_folder(cid), sha)
    if blob is None:
        raise HTTPException(status_code=404, detail="No such version")
    return FileResponse(blob, filename=name if download else None)


class RestoreVersionIn(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    version: int = Field(ge=1)


@app.post("/api/conversations/{cid}/versions/restore")
def restore_version(cid: str, body: RestoreVersionIn):
    from biomni_ui import versions

    folder = _session_folder(cid)
    rel = _in_session(folder, body.path)
    try:
        version = versions.restore(folder, rel, body.version)
    except LookupError as e:
        raise HTTPException(status_code=404, detail="No such version") from e
    return {"version": version, "versions": versions.versions_of(folder, rel)}


@app.get("/api/conversations/{cid}/provenance")
def file_provenance(cid: str, path: str, version: int):
    """How one version was made: the question and answer, code steps, tool-call log, environment and review of the task that wrote it."""
    from biomni_ui import versions

    folder = _session_folder(cid)
    path = _in_session(folder, path)
    rows = versions.versions_of(folder, path)
    found = next((v for v in rows if v["version"] == version), None)
    if found is None:
        raise HTTPException(status_code=404, detail="No such version")
    conv = store.get_conversation(cid) or {}
    task = next((t for t in conv.get("tasks", []) if t["id"] == found.get("task_id")), None)
    events = (task or {}).get("events", []) or []
    stamps = [float(e.get("ts") or 0) for e in events if e.get("ts")]
    receipts_all: list[dict] = []
    if stamps:
        lo, hi = min(stamps) - 2, max(stamps) + 2
        for r in receipts_mod_read(folder):
            try:
                at = time.mktime(time.strptime(str(r.get("time")), "%Y-%m-%d %H:%M:%S"))
            except (ValueError, TypeError):
                continue
            if lo <= at <= hi:
                receipts_all.append(r)
    try:
        return versions.provenance(folder, path, version, task, events, receipts_all)
    except LookupError as e:
        raise HTTPException(status_code=404, detail="No such version") from e


def receipts_mod_read(folder: Path) -> list[dict]:
    from biomni_ui import receipts

    return receipts.read_all(folder)


class AnnotationIn(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    text: str = Field(min_length=1, max_length=1000)
    quote: str = Field(default="", max_length=500)


@app.get("/api/conversations/{cid}/annotations")
def list_annotations(cid: str):
    from biomni_ui import annotations

    return {"items": annotations.list_items(_session_folder(cid))}


@app.post("/api/conversations/{cid}/annotations")
def add_annotation(cid: str, body: AnnotationIn):
    from biomni_ui import annotations

    try:
        annotations.add(_session_folder(cid), body.path, body.text, body.quote)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"items": annotations.list_items(_session_folder(cid))}


@app.delete("/api/conversations/{cid}/annotations/{item_id}")
def delete_annotation(cid: str, item_id: str):
    from biomni_ui import annotations

    if not annotations.delete(_session_folder(cid), item_id):
        raise HTTPException(status_code=404, detail="No such comment")
    return {"items": annotations.list_items(_session_folder(cid))}


class NotesIn(BaseModel):
    text: str = Field(max_length=20000)


@app.get("/api/conversations/{conv_id}/notes")
def get_notes(conv_id: str):
    text = store.get_notes(conv_id)
    if text is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"text": text}


@app.put("/api/conversations/{conv_id}/notes")
def put_notes(conv_id: str, body: NotesIn):
    if not store.set_notes(conv_id, body.text):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"ok": True}


# ---- published results: a self-contained HTML page of an answer, kept in ui_data/published -----------------------
PUBLISHED_DIR = ROOT / "ui_data" / "published"
# The page is the user's own saved answer; still, it is shown sandboxed with no scripts and no network requests.
PUBLISHED_CSP = "sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data: https:"


class PublishIn(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    html: str = Field(min_length=1, max_length=2_000_000)
    task_id: str = ""


@app.get("/api/published")
def list_published():
    return store.list_published()


@app.post("/api/published")
def publish(body: PublishIn):
    import uuid

    pub_id = uuid.uuid4().hex[:12]
    PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)
    (PUBLISHED_DIR / f"{pub_id}.html").write_text(body.html, encoding="utf-8")
    store.add_published(pub_id, body.title, body.task_id)
    return {"id": pub_id, "title": body.title}


@app.get("/api/published/{pub_id}/html")
def published_html(pub_id: str):
    if not pub_id.isalnum() or not (PUBLISHED_DIR / f"{pub_id}.html").exists():
        raise HTTPException(status_code=404, detail="This published result does not exist")
    return FileResponse(PUBLISHED_DIR / f"{pub_id}.html", media_type="text/html", headers={"Content-Security-Policy": PUBLISHED_CSP})


@app.delete("/api/published/{pub_id}")
def delete_published(pub_id: str):
    if not pub_id.isalnum() or not store.delete_published(pub_id):
        raise HTTPException(status_code=404, detail="This published result does not exist")
    try:
        (PUBLISHED_DIR / f"{pub_id}.html").unlink()
    except OSError:
        pass
    return {"ok": True}


@app.get("/api/usage")
def usage():
    return store.usage()


class PrefsIn(BaseModel):
    profile: dict = Field(default_factory=dict)
    prefs: dict = Field(default_factory=dict)


@app.get("/api/prefs")
def get_prefs():
    return {**prefs_store.load(), "areas": ui_prefs.AREAS}


@app.put("/api/prefs")
def put_prefs(body: PrefsIn):
    return {**prefs_store.save(body.model_dump()), "areas": ui_prefs.AREAS}


class ConnectorIn(BaseModel):
    enabled: bool


@app.get("/api/connectors")
def get_connectors():
    from biomni_ui import connectors

    return {"connectors": connectors.listing()}


@app.put("/api/connectors/{group_id}")
def put_connector(group_id: str, body: ConnectorIn):
    from biomni_ui import connectors

    if not connectors.set_enabled(group_id, body.enabled):
        raise HTTPException(status_code=404, detail="No such database connector")
    return {"connectors": connectors.listing()}


@app.get("/api/memory-notes")
def get_memory_notes(q: str = Query(default="", max_length=200), status: str = Query(default="", max_length=20)):
    """All notes, newest first; with q or status, only the matching ones."""
    from biomni_ui import notes

    if status and status not in (notes.APPROVED, notes.PROPOSED):
        raise HTTPException(status_code=400, detail="status must be approved or proposed")
    return {"items": notes.search(q, status or None)}


class MemoryNotePatch(BaseModel):
    text: str | None = Field(default=None, max_length=300)
    category: str | None = Field(default=None, max_length=40)
    project_id: str | None = Field(default=None, max_length=40)  # send null to make it apply to every project


@app.patch("/api/memory-notes/{item_id}")
def edit_memory_note(item_id: str, body: MemoryNotePatch):
    from biomni_ui import notes

    project_id = notes._UNSET
    if "project_id" in body.model_fields_set:
        project_id = body.project_id or None
        if project_id == "quick":
            project_id = None
        if project_id is not None and not any(p["id"] == project_id for p in store.list_projects()):
            raise HTTPException(status_code=400, detail="No such project")
    try:
        item = notes.update(item_id, text=body.text, category=body.category, project_id=project_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if item is None:
        raise HTTPException(status_code=404, detail="No such remembered item")
    return {"item": item, "items": notes.list_items()}


@app.delete("/api/memory-notes/{item_id}")
def delete_memory_note(item_id: str):
    from biomni_ui import notes

    if not notes.delete(item_id):
        raise HTTPException(status_code=404, detail="No such remembered item")
    return {"items": notes.list_items()}


class MemoryNoteIn(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    project_id: str | None = Field(default=None, max_length=40)  # None: every project
    category: str = Field(default="General", max_length=40)


@app.post("/api/memory-notes")
def add_memory_note(body: MemoryNoteIn):
    from biomni_ui import notes

    project_id = body.project_id or None
    if project_id == "quick":  # the quick-task area is not a project: its notes apply to every project
        project_id = None
    if project_id is not None and not any(p["id"] == project_id for p in store.list_projects()):
        raise HTTPException(status_code=400, detail="No such project")
    notes.add(body.text.strip(), project_id, category=body.category)
    return {"items": notes.list_items()}


@app.delete("/api/projects/{project_id}/memory")
def clear_project_memory(project_id: str):
    """Forget everything remembered for one project (notes for all projects are kept)."""
    from biomni_ui import notes

    return {"removed": notes.delete_project(project_id), "items": notes.list_items()}


@app.get("/api/projects/{project_id}/generated")
def project_generated_files(project_id: str):
    if project_id != "quick" and not any(p["id"] == project_id for p in store.list_projects()):
        raise HTTPException(status_code=404, detail="Project not found")
    return {"files": store.generated_files(project_id)}


@app.post("/api/memory-notes/{item_id}/approve")
def approve_memory_note(item_id: str):
    from biomni_ui import notes

    if not notes.approve(item_id):
        raise HTTPException(status_code=404, detail="No such remembered item")
    return {"items": notes.list_items()}


@app.get("/api/work-log")
def get_work_log(project_id: str = Query(default="", max_length=40), limit: int = Query(default=50, ge=1, le=200)):
    """What the tasks of a project (or of all projects) did, newest first: the project's own record of its work."""
    from biomni_ui import worklog

    return {"items": worklog.list_items(project_id or None, limit)}


@app.delete("/api/work-log")
def clear_work_log(project_id: str = Query(default="", max_length=40)):
    """Forget the work log of one project, or of all projects when no project is given."""
    from biomni_ui import worklog

    return {"removed": worklog.delete(project_id or None)}


class ProjectSettingsIn(BaseModel):
    context: str = Field(default="", max_length=ui_prefs.MAX_CONTEXT_CHARS)
    instructions: list[str] = Field(default_factory=list, max_length=ui_prefs.MAX_INSTRUCTIONS)
    skills: list[str] = Field(default_factory=list, max_length=20)
    files: list[str] = Field(default_factory=list, max_length=20)  # upload names
    tools_off: list[str] = Field(default_factory=list, max_length=10)  # optional tools switched off for every task in the project
    memory_on: bool = True  # off: nothing remembered is used in the project's tasks


@app.get("/api/projects/{project_id}/settings")
def get_project_settings(project_id: str):
    if project_id != "quick" and not any(p["id"] == project_id for p in store.list_projects()):
        raise HTTPException(status_code=404, detail="Project not found")
    return store.get_project_settings(project_id)


@app.put("/api/projects/{project_id}/settings")
def put_project_settings(project_id: str, body: ProjectSettingsIn):
    value = ui_prefs.clean_project_settings(body.model_dump())
    known = {s["id"] for s in skills.list()}
    value["skills"] = [x for x in value["skills"] if x in known]
    uploaded = {p.name for p in _upload_dir().iterdir() if p.is_file()} if _upload_dir().exists() else set()
    value["files"] = [x for x in value["files"] if x in uploaded]  # only files that are really uploaded
    if not store.set_project_settings(project_id, value):
        raise HTTPException(status_code=404, detail="Project not found")
    return value


class HiddenIn(BaseModel):
    hidden: bool


@app.put("/api/models/{model_id}/hidden")
def set_model_hidden(model_id: str, body: HiddenIn):
    if not models.set_hidden(model_id, body.hidden):
        raise HTTPException(status_code=400, detail="This model does not exist, or it cannot be hidden from the picker")
    return _models_view()


@app.get("/api/connections")
def connections():
    """What this installation is connected to, without exposing any secret."""
    return {
        "chatgpt": {"logged_in": chatgpt_api.is_logged_in()},
        "providers": providers.list(),
        "data_path": str(_config().path),
        "workdir": str(Path.cwd()),
    }


@app.get("/api/data/info")
def data_info():
    def folder_size(p: Path) -> int:
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.exists() else 0

    db = ROOT / "ui_data" / "biomni_ui.db"
    return {
        **store.data_info(),
        "db_bytes": db.stat().st_size if db.exists() else 0,
        "uploads_bytes": folder_size(Path(_config().path) / "uploads"),
        "published_bytes": folder_size(PUBLISHED_DIR),
    }


@app.get("/api/data/export")
def data_export():
    from fastapi.responses import Response

    body = json.dumps(store.export_all(), ensure_ascii=False)
    return Response(body, media_type="application/json", headers={"Content-Disposition": 'attachment; filename="biomni-lite-export.json"'})


class ClearIn(BaseModel):
    confirm: str


@app.post("/api/data/clear")
def data_clear(body: ClearIn):
    """Delete every conversation. Needs the exact confirmation word ("clear"; the old Chinese word is still accepted), and refuses while a task runs."""
    if body.confirm not in ("clear", "清空"):
        raise HTTPException(status_code=400, detail='Type "clear" to confirm')
    if manager.busy:
        raise HTTPException(status_code=409, detail="A task is running; stop it first")
    return {"deleted": store.delete_all_conversations()}


@app.get("/api/runtime")
def runtime_info():
    """What the agent's code runs on, for the compute panel."""
    import platform
    import sys

    cfg = _config()
    return {
        "python": platform.python_version(),
        "platform": f"{platform.system()} {platform.release()}",
        "executable": sys.executable,
        "workdir": str(Path.cwd()),
        "data_path": str(cfg.path),
        "timeout_seconds": getattr(cfg, "timeout_seconds", None),
        "model": (_active_entry() or {}).get("model", cfg.llm),
        "source": cfg.source,
    }


@app.post("/api/files/zip")
def zip_files(body: ZipIn):
    """Several result files as one download (only files the workspace rules allow)."""
    import io as _io
    import zipfile

    buf = _io.BytesIO()
    names: set[str] = set()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for path in body.paths[:100]:
            real = files.resolve(path, manager.roots)
            if real is None:
                continue
            name, i = real.name, 1
            while name in names:
                i += 1
                name = f"{real.stem}-{i}{real.suffix}"
            names.add(name)
            z.write(real, name)
    if not names:
        raise HTTPException(status_code=404, detail="No file is available to download")
    from fastapi.responses import Response

    return Response(buf.getvalue(), media_type="application/zip", headers={"Content-Disposition": 'attachment; filename="results.zip"'})


@app.delete("/api/conversations/{conv_id}")
def delete_conversation(conv_id: str):
    if manager.running_in(conv_id):
        raise HTTPException(status_code=409, detail="A task is running in this conversation. Stop it first.")
    store.delete_conversation(conv_id)
    return {"ok": True}


def _agent_tools(agent) -> list[dict]:
    reg = getattr(agent, "tool_registry", None)
    return list(getattr(reg, "tools", []) or [])


@app.get("/api/mentions")
def search_mentions(q: str = Query("", max_length=80)):
    if not manager.agent_ready:
        return []
    agent = manager.agent()
    return mentions.search(
        q,
        skills=skills,
        tools=_agent_tools(agent),
        data_lake=dict(getattr(agent, "data_lake_dict", {}) or {}),
        roots=manager.roots,
    )


@app.get("/api/resources")
def resources():
    """Everything the agent can use: tools (by module), datasets in the data lake, and software libraries."""
    if not manager.agent_ready:
        return {"ready": False, "tools": [], "data": [], "libraries": []}
    agent = manager.agent()
    tools = [
        {"name": t.get("name", ""), "description": (t.get("description") or "").strip()[:300], "module": str(t.get("module") or "")}
        for t in _agent_tools(agent)
    ]
    try:  # static check of every stock tool (cached for a day): can it run here, and if not, why
        health = {r["name"]: r for r in tool_health.load(ROOT / "ui_data" / "tool_health.json")}
    except Exception:
        health = {}
    for t in tools:
        h = health.get(t["name"])
        t["status"] = h["status"] if h else "available"  # tools we added ourselves were run against the real services
        t["note"] = "; ".join(([f"missing: {', '.join(h['missing'])}"] if h and h["missing"] else []) + (h["needs"] if h else []))
    summary = tool_health.summary([{"status": t["status"]} for t in tools])
    data = [{"name": k, "description": (v or "").strip()[:300]} for k, v in dict(getattr(agent, "data_lake_dict", {}) or {}).items()]
    libs = [{"name": k, "description": (v or "").strip()[:300]} for k, v in dict(getattr(agent, "library_content_dict", {}) or {}).items()]
    return {"ready": True, "tools": tools, "data": data, "libraries": libs, "tool_summary": summary}


# ---- scheduled tasks and skill import ------------------------------------------------------------

class ScheduleIn(BaseModel):
    name: str = Field(default="", max_length=80)
    prompt: str = Field(min_length=1, max_length=20000)
    project_id: str | None = Field(default=None, max_length=40)
    kind: str = Field(default="daily", pattern="^(every|daily)$")
    minutes: int | None = None
    time: str | None = Field(default=None, max_length=5)  # HH:MM, local time, for kind "daily"
    enabled: bool = True


class SkillImportIn(BaseModel):
    url: str = Field(min_length=8, max_length=2000)


class GitHubTokenIn(BaseModel):
    token: str | None = Field(default=None, max_length=300)


@app.get("/api/credentials/github")
def github_token_state():
    """Whether a GitHub token is stored. The value itself is never sent back to the page."""
    from biomni_ui import github_skills

    return {"set": github_skills.get_token() is not None}


@app.put("/api/credentials/github")
def set_github_token(body: GitHubTokenIn):
    from biomni_ui import github_skills

    return {"set": github_skills.set_token(body.token)}


@app.get("/api/skill-updates")  # not under /api/skills/: that prefix is taken by /api/skills/{skill_id}
def check_skill_updates():
    """Imported GitHub skills that changed upstream. Asks GitHub; changes nothing until the user applies them."""
    import httpx

    from biomni_ui import github_skills

    try:
        rows = github_skills.check_updates(skills, token=github_skills.get_token())
    except (ValueError, httpx.HTTPError) as e:
        raise HTTPException(status_code=502, detail=str(e) or f"Could not reach GitHub ({type(e).__name__})") from e
    return {"updates": rows}


class SkillUpdateIn(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=50)


@app.post("/api/skill-updates/apply")
def apply_skill_updates(body: SkillUpdateIn):
    import httpx

    from biomni_ui import github_skills

    try:
        done = github_skills.apply_updates(skills, body.ids, token=github_skills.get_token())
    except (ValueError, httpx.HTTPError) as e:
        raise HTTPException(status_code=502, detail=str(e) or f"Could not reach GitHub ({type(e).__name__})") from e
    _resync_skills()
    return {"updated": done}


def _start_scheduled(job: dict):
    """Start one scheduled run in auto mode. Raises schedules.SkipRun while a task is running, so the job is retried later."""
    try:
        task = manager.start(job["prompt"], None, "", mode="auto")
    except Busy as e:
        raise schedules.SkipRun(str(e)) from e
    project_id = job.get("project_id") or "quick"
    if project_id != "quick" and any(p["id"] == project_id for p in store.list_projects()):
        store.set_project(task.conversation_id, project_id)
    return task


def _schedule_spec(body: ScheduleIn) -> dict:
    try:
        return schedules.validate(body.kind, body.minutes, body.time)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/api/schedules")
def list_schedules():
    return schedule_store.list()


@app.post("/api/schedules")
def create_schedule(body: ScheduleIn):
    return schedule_store.create(body.name, body.prompt, body.project_id, _schedule_spec(body), body.enabled)


@app.put("/api/schedules/{job_id}")
def update_schedule(job_id: str, body: ScheduleIn):
    job = schedule_store.update(job_id, body.name, body.prompt, body.project_id, _schedule_spec(body), body.enabled)
    if job is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return job


@app.delete("/api/schedules/{job_id}")
def delete_schedule(job_id: str):
    if not schedule_store.delete(job_id):
        raise HTTPException(status_code=404, detail="Schedule not found")
    return {"ok": True}


@app.post("/api/schedules/{job_id}/run")
def run_schedule_now(job_id: str):
    job = schedule_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    try:
        task = _start_scheduled(job)
    except schedules.SkipRun as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    schedule_store.mark(job_id, last_status="started", last_run=time.time(), last_task_id=task.id, last_conversation_id=task.conversation_id)
    return {"id": task.id, "conversation_id": task.conversation_id}


@app.post("/api/skills/import")
def import_skill(body: SkillImportIn):
    import httpx

    try:
        from biomni_ui import github_skills

        skill = skill_import.import_skill(skills, body.url, token=github_skills.get_token())
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Could not download the file ({type(e).__name__})") from e
    _resync_skills()
    return skill


# ---- community library (curated) ---------------------------------------------------------------

@app.get("/api/community")
def community_search(q: str = Query(default="", max_length=200), kind: str = Query(default="", max_length=20)):
    """The curated community entries, filtered by words and kind (skills, tools, lists)."""
    from biomni_ui import community

    if kind and kind not in community.KINDS:
        raise HTTPException(status_code=400, detail="kind must be skills, tools or lists")
    cat = community.catalog()
    return {"checked_on": cat.get("checked_on", ""), "note": cat.get("note", ""), "items": community.search(q, kind or None)}


@app.get("/api/community/{entry_id}/skills")
def community_skills(entry_id: str):
    """The SKILL.md files in one skill collection, and which of them are already in the skill library."""
    from biomni_ui import community, github_skills

    e = community.entry(entry_id)
    if e is None:
        raise HTTPException(status_code=404, detail="No such library entry")
    try:
        files = community.skill_files(e, token=github_skills.get_token())
    except ValueError as err:
        raise HTTPException(status_code=502, detail=str(err)) from err
    except httpx.HTTPError as err:
        raise HTTPException(status_code=502, detail=f"Could not list the repository ({type(err).__name__})") from err
    present = {s.get("id") for s in skills.list()}
    return {"entry": e, "files": [{**f, "url": community.blob_url(e, f["path"])} for f in files], "present": sorted(present)}


class CommunityInstallIn(BaseModel):
    paths: list[str] = Field(default_factory=list, max_length=50)  # community.MAX_INSTALL


@app.post("/api/community/{entry_id}/install")
def community_install(entry_id: str, body: CommunityInstallIn):
    """Add the chosen skills from a collection to the skill library. Each one is checked and saved like an import from a link."""
    from biomni_ui import community, github_skills

    e = community.entry(entry_id)
    if e is None:
        raise HTTPException(status_code=404, detail="No such library entry")
    try:
        results = community.install(e, body.paths, skills, github_skills.get_token(), skill_import.import_skill)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    except httpx.HTTPError as err:
        raise HTTPException(status_code=502, detail=f"Could not download the skills ({type(err).__name__})") from err
    _resync_skills()
    return {"results": results, "added": sum(1 for r in results if r["ok"])}


# ---- community hub (search, scan, install) ------------------------------------------------------

@app.get("/api/hub/search")
def hub_search(q: str = Query(default="", max_length=200), kind: str = Query(default="", max_length=20), trust: str = Query(default="", max_length=20)):
    """Skills (from the index), tools, databases and software (from the curated list) matching the words. Each skill says whether it is installed."""
    from biomni_ui import community, hub

    if kind and kind not in ("skills", "tools", "lists", "databases", "software"):
        raise HTTPException(status_code=400, detail="kind must be skills, tools, lists, databases or software")
    idx = hub.index()
    have = hub.installed_urls()
    items = hub.search(q, kind or None, trust or None)
    for it in items:
        if it.get("kind") == "skills":
            it["installed"] = it.get("url") in have
    return {"items": items, "count": len(items), "built_on": idx.get("built_on", ""), "indexed": idx.get("count", 0), "skipped": idx.get("skipped", 0),
            "checked_on": community.catalog().get("checked_on", "")}


@app.post("/api/hub/refresh")
def hub_refresh():
    """Rebuild the skills index from GitHub in the background. The page follows the progress with /api/hub/status."""
    from biomni_ui import hub

    return {"started": hub.start_refresh(), "status": hub.status()}


@app.get("/api/hub/status")
def hub_status():
    from biomni_ui import hub

    return hub.status()


class HubUrlIn(BaseModel):
    url: str = Field(min_length=10, max_length=400)
    force: bool = False


@app.post("/api/hub/inspect")
def hub_inspect(body: HubUrlIn):
    """Download a skill and scan it, to read the findings before deciding. Nothing is installed."""
    import httpx

    from biomni_ui import hub

    try:
        res = hub.inspect(body.url.strip())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Could not download the skill ({type(e).__name__})") from e
    return res


@app.post("/api/hub/install")
def hub_install(body: HubUrlIn):
    """Scan the skill and add it to the library when the install policy allows it. A caution verdict needs force (you confirm the findings);
    a dangerous verdict is refused whatever you send. Every attempt is written to the audit log."""
    import httpx

    from biomni_ui import github_skills, hub

    try:
        result = hub.install(body.url.strip(), force=body.force, store=skills, fetch_text=None)
    except PermissionError as e:
        import json as _json

        raise HTTPException(status_code=409, detail=_json.loads(str(e))) from e
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail={"reason": str(e)}) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Could not download the skill ({type(e).__name__})") from e
    _resync_skills()
    return result


# ---- agent profiles -----------------------------------------------------------------------------

class AgentIn(BaseModel):
    name: str = Field(default="", max_length=60)
    model_id: str | None = Field(default=None, max_length=120)  # empty: the model in use in Settings
    effort: str | None = Field(default=None, max_length=20)  # empty: the model's default
    mode: str = Field(default="ask", max_length=10)
    tools_off: list[str] = Field(default_factory=list, max_length=10)
    skills: list[str] = Field(default_factory=list, max_length=20)
    instructions: str = Field(default="", max_length=agents.MAX_INSTRUCTIONS)


def _agent_fields(body: AgentIn) -> dict:
    try:
        return agents.clean(body.model_dump(), {m["id"] for m in models.list()}, EFFORTS)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/api/agents")
def list_agents():
    return agent_store.list()


@app.post("/api/agents")
def create_agent(body: AgentIn):
    try:
        return agent_store.create(_agent_fields(body))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.put("/api/agents/{profile_id}")
def update_agent(profile_id: str, body: AgentIn):
    updated = agent_store.update(profile_id, _agent_fields(body))
    if updated is None:
        raise HTTPException(status_code=404, detail="Agent profile not found")
    return updated


@app.delete("/api/agents/{profile_id}")
def delete_agent(profile_id: str):
    if not agent_store.delete(profile_id):
        raise HTTPException(status_code=404, detail="Agent profile not found")
    return {"ok": True}


@app.get("/api/conversations/{cid}/notebook")
def session_notebook(cid: str):
    """The session as cells (questions, code steps with output, tool calls, answers), in order. Built from stored events only."""
    from biomni_ui import notebook

    conv = store.get_conversation(cid)
    if conv is None:
        raise HTTPException(status_code=404, detail="No such session")
    return {"title": conv.get("title", ""), "environment": notebook.environment(), "cells": notebook.build(conv)}


SESSION_CONTEXT_CHARS = 4000


def _session_digest(conversation_id: str) -> str:
    """The recent questions and answers of one earlier session, as context for a new task (capped in size). Empty if there is none."""
    conv = store.get_conversation(conversation_id) if conversation_id else None
    if not conv:
        return ""
    lines: list[str] = []
    for t in (conv.get("tasks") or [])[-4:]:
        answer = next((e.get("text", "") for e in t.get("events", []) if e.get("type") == "answer"), "")
        lines.append(f"Q: {str(t.get('prompt') or '')[:400]}")
        if answer:
            lines.append(f"A: {str(answer)[:900]}")
    if not lines:
        return ""
    body = "\n".join(lines)[:SESSION_CONTEXT_CHARS]
    return (f"The user referred to an earlier session “{conv.get('title', '')}”. Its recent exchanges follow, as context for this request "
            f"(do not repeat them unless asked):\n{body}")


@app.post("/api/tasks")
def create_task(body: NewTask):
    project_id = store.conversation_project(body.conversation_id) if body.conversation_id else (body.project_id or "quick")
    if project_id != "quick" and not any(p["id"] == project_id for p in store.list_projects()):
        project_id = "quick"
    project = store.get_project_settings(project_id)
    profile = agent_store.get(body.agent_id) if body.agent_id else None
    if body.agent_id and profile is None:
        raise HTTPException(status_code=400, detail="No such agent profile")
    mode = profile["mode"] if profile else body.mode
    tools_off = agents.tools_off_for(profile, project)

    extra = ""
    if body.approval:
        extra = assist.approved_prompt(body.prompt, body.approval.plan, body.approval.answers)
    # skills the project and the agent profile attach to every new task are mentioned like skills the user picked with "@"
    wanted = list(body.mentions)
    have = {(m.get("kind"), m.get("id")) for m in wanted}
    attached = list(project["skills"]) + list((profile or {}).get("skills", []))
    wanted += [{"kind": "skill", "id": sid} for sid in dict.fromkeys(attached) if ("skill", sid) not in have]
    for m in wanted:  # a past session picked with "#": its recent exchanges go in as context
        if m.get("kind") == "session":
            digest = _session_digest(str(m.get("id") or ""))
            if digest:
                extra = "\n\n".join(x for x in (extra, digest) if x)
    if wanted and manager.agent_ready:
        agent = manager.agent()
        picked = mentions.to_prompt(
            wanted,
            skills=skills,
            tool_names={t.get("name", "") for t in _agent_tools(agent)},
            data_names=set(getattr(agent, "data_lake_dict", {}) or {}),
            roots=manager.roots,
        )
        extra = "\n\n".join(x for x in (extra, picked) if x)
    prefs = prefs_store.load()
    recent = store.recent_files(project_id, body.conversation_id) if prefs["prefs"]["use_last_results"] else []
    brief = ui_prefs.briefing(prefs, project, recent)
    extra = "\n\n".join(x for x in (extra, brief) if x)
    project_files = [str(_upload_dir() / f) for f in project.get("files", []) if (_upload_dir() / f).is_file()]
    if project_files:  # the project's own files: the agent opens them with python or bash when they are relevant
        extra = "\n\n".join(x for x in (extra, "Files this project has (uploaded for it; open them when relevant):\n" + "\n".join(f"- {p}" for p in project_files)) if x)
    pending, folder = [], None
    if body.conversation_id:  # comments left on result files since the last message go with this one
        from biomni_ui import annotations

        folder = workdir.conversation_dir(body.conversation_id)
        pending = annotations.take_pending(folder)
        extra = "\n\n".join(x for x in (extra, annotations.as_prompt_text(pending)) if x)
    try:
        task = manager.start(body.prompt.strip(), body.conversation_id, extra, mode=mode, agent=profile, tools_off=tools_off)
    except Busy as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    if pending and folder is not None:
        from biomni_ui import annotations

        annotations.mark_sent(folder, [a["id"] for a in pending], task.id)
    if not body.conversation_id and project_id != "quick":
        store.set_project(task.conversation_id, project_id)
    return {"id": task.id, "conversation_id": task.conversation_id}


def _earlier_turns(conversation_id: str | None) -> list[tuple[str, str]]:
    conv = store.get_conversation(conversation_id) if conversation_id else None
    out = []
    for t in (conv or {}).get("tasks", []):
        answer = next((e["text"] for e in t["events"] if e["type"] == "answer"), "")
        if answer:
            out.append((t["prompt"], answer[:800]))
    return out[-3:]


@app.post("/api/plan")
def draft_plan(body: PlanRequest):
    """Draft a plan (and clarifying questions) for the user to edit and approve before anything runs."""
    _llm()  # the agent must be ready; the plan itself is drafted by the planner model chosen in Settings (or the main model)
    llm = _planner_llm()
    try:
        return assist.draft_plan(llm, body.prompt.strip(), _earlier_turns(body.conversation_id))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Plan drafting failed: {type(e).__name__}: {e}") from e


@app.post("/api/tasks/{task_id}/cancel")
def cancel_task(task_id: str):
    if not manager.cancel(task_id):
        raise HTTPException(status_code=404, detail="Task not found or already finished")
    return {"ok": True}


class PermissionAnswerIn(BaseModel):
    id: str = Field(min_length=4, max_length=40)
    choice: str = Field(pattern="^(once|conversation|project|global|deny)$")


@app.post("/api/tasks/{task_id}/permission")
def answer_permission(task_id: str, body: PermissionAnswerIn):
    """The user's answer to a database-permission request raised by a task (see permissions.py)."""
    from biomni_ui import permissions

    if not permissions.answer(body.id, body.choice):
        raise HTTPException(status_code=400, detail="Could not record the answer")
    return {"ok": True}


@app.get("/api/grants")
def list_grants():
    from biomni_ui import permissions

    return {"grants": permissions.listing()}


@app.delete("/api/grants")
def revoke_grant(scope: str, tool: str, key: str = ""):
    from biomni_ui import permissions

    if not permissions.remove(scope, tool, key or None):
        raise HTTPException(status_code=404, detail="No such standing permission")
    return {"grants": permissions.listing()}


def _finished_task(task_id: str) -> tuple[dict, list[dict], list[tuple[str, str]]]:
    conv_task = store.get_task(task_id)
    if conv_task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if conv_task["status"] == "running":
        raise HTTPException(status_code=409, detail="The task is still running")
    conv = store.get_conversation(conv_task["conversation_id"])
    events, earlier = [], []
    for t in conv["tasks"]:
        if t["id"] == task_id:
            events = t["events"]
            break
        answer = next((e["text"] for e in t["events"] if e["type"] == "answer"), "")
        if answer:
            earlier.append((t["prompt"], answer[:800]))
    return conv_task, events, earlier


def _llm():
    if not manager.agent_ready:
        raise HTTPException(status_code=503, detail="The agent has not finished loading")
    return manager.agent().llm


@app.post("/api/tasks/{task_id}/review")
def review_task(task_id: str):
    task, events, earlier = _finished_task(task_id)
    s = ui_settings.load(SETTINGS_FILE)  # the reviewer model and level chosen in Settings (None: the main model)
    reviewer = _role_entry("reviewer_model_id")
    eff = s.get("reviewer_effort")
    llm = _build_llm(entry=reviewer, effort=eff, search=False) if (reviewer or eff) else _llm()
    try:
        text = assist.review(llm, task["prompt"], events, earlier)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Review call failed: {type(e).__name__}: {e}") from e
    return manager.add_event(task_id, {"type": "review", "text": text})


@app.post("/api/tasks/{task_id}/suggest")
def suggest_task(task_id: str):
    task, events, earlier = _finished_task(task_id)
    llm = _llm()
    try:
        items = assist.suggest(llm, task["prompt"], events, earlier)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Generating follow-up questions failed: {type(e).__name__}: {e}") from e
    return manager.add_event(task_id, {"type": "suggestions", "items": items})


class RefItem(BaseModel):
    kind: str
    id: str = Field(max_length=500)


class RefRequest(BaseModel):
    items: list[RefItem] = Field(max_length=60)


@app.post("/api/refs/resolve")
def resolve_refs(body: RefRequest):
    """Turn PMIDs / DOIs / URLs cited in an answer into title, authors, journal and year (cached)."""
    return resolver.resolve([i.model_dump() for i in body.items])


@app.get("/api/files")
def get_file(p: str = Query(...), download: bool = False):
    real = files.resolve(p, manager.roots)
    if real is None:
        raise HTTPException(status_code=404, detail="File not found or access is not allowed")
    headers = {"Content-Security-Policy": "sandbox"} if real.suffix.lower() == ".html" else {}
    return FileResponse(real, headers=headers, filename=real.name if download else None)


class OpenIn(BaseModel):
    path: str
    action: str = "open"  # "open": the program this machine uses for that file type; "folder": show it in the file manager


@app.post("/api/open")
def open_on_this_machine(body: OpenIn, request: Request):
    """Open a result file with the default program, or show it in its folder. The app runs on the user's own computer; only requests from it are served."""
    if not request.client or request.client.host not in ("127.0.0.1", "::1", "localhost"):
        raise HTTPException(status_code=403, detail="Files can only be opened on the computer running this app")
    real = files.resolve(body.path, manager.roots)
    if real is None:
        raise HTTPException(status_code=404, detail="File not found or access is not allowed")
    try:
        if body.action == "folder":
            subprocess.Popen(["explorer", f"/select,{real}"])
        else:
            os.startfile(str(real))  # type: ignore[attr-defined]  # Windows: the associated program
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not open: {type(e).__name__}: {e}") from e
    return {"ok": True, "path": str(real)}


def _upload_dir() -> Path:
    d = Path(_config().path) / "uploads"
    d.mkdir(parents=True, exist_ok=True)
    return d


@app.get("/api/uploads")
def list_uploads():
    out = []
    for p in sorted(_upload_dir().iterdir(), key=lambda x: -x.stat().st_mtime):
        if p.is_file() and p.suffix.lower() in files.ALLOWED_EXT:
            out.append(files.describe(p.resolve()))
    return out


@app.post("/api/uploads")
async def upload_file(file: UploadFile = File(...)):
    try:
        name = files.safe_upload_name(file.filename or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    dest = _upload_dir() / name
    size = 0
    try:
        with dest.open("wb") as f:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > files.MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="File is larger than 100 MB")
                f.write(chunk)
    except HTTPException:
        dest.unlink(missing_ok=True)
        raise
    return files.describe(dest.resolve())


@app.delete("/api/uploads/{name}")
def delete_upload(name: str):
    try:
        safe = files.safe_upload_name(name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    target = _upload_dir() / safe
    if not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    target.unlink()
    return {"ok": True}


class Feedback(BaseModel):
    vote: str | None = Field(default=None, pattern="^(up|down)$")


@app.post("/api/tasks/{task_id}/feedback")
def task_feedback(task_id: str, body: Feedback):
    """Record a thumbs up / down (or clear it with null); the latest feedback event of a task wins."""
    if store.get_task(task_id) is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return manager.add_event(task_id, {"type": "feedback", "vote": body.vote})


@app.get("/api/tasks/{task_id}/events")
def task_events(task_id: str, start: int = Query(0, alias="from"), last_event_id: str | None = Header(None)):
    task = manager.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if last_event_id and last_event_id.isdigit():
        start = int(last_event_id) + 1

    def gen():
        for ev in task.stream(start):
            if ev is None:
                yield ": ping\n\n"
            elif ev["type"] == "draft":  # live text of the call in progress: no id, not part of the stored log
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
            else:
                yield f"id: {ev['seq']}\ndata: {json.dumps(ev, ensure_ascii=False)}\n\n"

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(gen(), media_type="text/event-stream", headers=headers)


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
