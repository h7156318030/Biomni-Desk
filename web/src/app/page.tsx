"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CopyButton, EventView, PlanView, ProcessGroup } from "@/components/events";
import { LiveDraft, StepCards } from "@/components/steps";
import { SkillDraftDialog } from "@/components/skill-draft";
import { ResultsPanel } from "@/components/results-panel";
import { ArtifactDetail } from "@/components/artifact-detail";
import { ModePicker } from "@/components/mode-picker";
import { Drive } from "@/components/drive";
import { FilePreview, PreviewContext } from "@/components/file-preview";
import { Gallery } from "@/components/gallery";
import { SavedPrompts, useSavedPrompts } from "@/components/saved-prompts";
import { ShortcutHelp, isTyping } from "@/components/shortcuts";
import { SHORTCUTS_EVENT } from "@/components/rail";
import { HistoryList } from "@/components/history";
import { takePrefill } from "@/lib/prefill";
import { tr, useI18n } from "@/lib/i18n";
import { AttachMenu } from "@/components/attach-menu";
import { Tips } from "@/components/tips";
import { LayoutMenu, PANELS, readPanels, type PanelId } from "@/components/layout-menu";
import { ALL, ProjectSwitcher, TransferMenu } from "@/components/project-switcher";
import { ShareDialog } from "@/components/share-dialog";
import { NotesPanel } from "@/components/notes-panel";
import { ComputePanel, callSummary } from "@/components/compute-panel";
import { ProgressBar, SideSection, SourceList } from "@/components/side-panel";
import { relativeTime } from "@/lib/time";
import { SlashMenu, filterCommands, promptHistory, slashQuery, type SlashCommand } from "@/components/slash";
import { buildLedger } from "@/lib/citations";
import { PlanDraft, type Approval, type Draft } from "@/components/plan-draft";
import { MentionMenu, activeTrigger } from "@/components/mention-box";
import { FollowUps } from "@/components/followups";
import { AskChoices } from "@/components/askchoices";
import { PermissionCard } from "@/components/permission-card";
import { ModelPicker } from "@/components/model-picker";
import {
  cancelTask,
  createTask,
  searchSessions,
  type SearchHit,
  createProject,
  deleteConversation,
  getPrefs,
  deleteProject,
  listProjects,
  moveConversation,
  renameProject,
  type Project,
  uploadFile,
  draftPlan,
  getConversation,
  getHealth,
  listConversations,
  renameConversation,
  reviewTask,
  subscribe,
  sendFeedback,
  suggestTask,
  type Artifact,
  type ConversationSummary,
  type Health,
  type Mention,
  type TaskRecord,
} from "@/lib/api";

// Status and label texts are English source strings; the UI translates them at render time.
const STATE_LABEL: Record<string, string> = {
  starting: "Starting the agent…",
  queued: "Queued, waiting for a free agent…",
  retrieving: "Choosing relevant tools…",
  running: "The agent is thinking…",
};
/** Pictures and videos the task's steps produced, each once, in the order they appeared. */
function mediaOf(events: TaskRecord["events"]): Artifact[] {
  const seen = new Set<string>();
  const out: Artifact[] = [];
  for (const e of events) {
    if (e.type !== "observation") continue;
    for (const a of ((e as { artifacts?: Artifact[] }).artifacts ?? [])) {
      if ((a.kind === "image" || a.kind === "video") && !seen.has(a.path)) {
        seen.add(a.path);
        out.push(a);
      }
    }
  }
  return out;
}
const PROCESS = new Set(["reasoning", "code", "observation", "notice", "tool", "subagent"]);

/** Consecutive working steps are drawn together on a left rule; answers and reviews stand alone. */
function groupEvents(events: TaskRecord["events"]) {
  const groups: { process: boolean; items: TaskRecord["events"] }[] = [];
  for (const ev of events) {
    const process = PROCESS.has(ev.type);
    const last = groups[groups.length - 1];
    if (process && last?.process) last.items.push(ev);
    else groups.push({ process, items: [ev] });
  }
  return groups;
}

const REVISE_PROMPT = "Work through the independent review above point by point: for each point, check the evidence again; where it holds, correct the answer, and where it does not, say why. Then give the full revised answer and list what changed.";
const HIDDEN = new Set(["status", "tools", "plan", "done", "suggestions", "feedback", "llm", "ask", "permission"]);

/** How a task runs: plan = the plan is approved first, then it runs without questions; ask = it plans and runs, asking when unsure; auto = no plan approval, no questions. */
type TaskMode = "plan" | "ask" | "auto";
const TASK_MODES: { id: TaskMode; label: string; hint: string }[] = [
  { id: "plan", label: "Manual plan, auto run", hint: "Draft a plan first; it runs automatically once you approve. No questions during the run" },
  { id: "ask", label: "Auto plan, approve complex tasks", hint: "The model plans; a complex task waits for your approval of the plan, and it asks when unsure" },
  { id: "auto", label: "Fully automatic", hint: "The model plans, judges and runs by itself, with no questions" },
];
const isTaskMode = (v: string | null): v is TaskMode => v === "plan" || v === "ask" || v === "auto";

function runsOfCount(events: TaskRecord["events"]): number {
  return events.filter((e) => e.type === "code").length;
}

/** A greeting key for the time of day; translate it when shown. */
function greeting(): string {
  const h = new Date().getHours();
  return h < 6 ? "Working late" : h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

function clock(sec: number): string {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  return h ? `${h}h ${m}m ${s}s` : m ? `${m}m ${s}s` : `${s}s`;
}

export default function Home() {
  const { t } = useI18n();
  const [health, setHealth] = useState<Health | null>(null);
  const [offline, setOffline] = useState(false);
  const [convs, setConvs] = useState<ConversationSummary[]>([]);
  const [search, setSearch] = useState("");
  const [sidebarView, setSidebarView] = useState<"project" | "time">("project");  // sessions grouped under their projects (as Claude Science), or by day
  const [hits, setHits] = useState<SearchHit[] | null>(null);  // sessions matching the search text, across every project
  useEffect(() => {
    try {
      const v = localStorage.getItem("sidebarView");
      if (v === "time" || v === "project") setSidebarView(v);
    } catch {}
  }, []);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [turns, setTurns] = useState<TaskRecord[]>([]);
  const [prompt, setPrompt] = useState("");
  const [liveDraft, setLiveDraft] = useState("");
  const [checking, setChecking] = useState(false); // the source check sent the answer back to the model: the old draft stays up until the revision streams in
  const [reviewing, setReviewing] = useState<string | null>(null);
  const [skillFor, setSkillFor] = useState<string | null>(null);  // the finished task whose method is being saved as a skill
  const [skillNote, setSkillNote] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [picked, setPicked] = useState<Mention[]>([]);
  const [menu, setMenu] = useState<{ start: number; query: string; trigger: "@" | "#" | "/" } | null>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const [drawer, setDrawer] = useState<"left" | "right" | null>(null);
  const [mode, setMode] = useState<TaskMode>("ask");
  const planMode = mode === "plan";
  const [draft, setDraft] = useState<Draft | null>(null);
  const [drafting, setDrafting] = useState(false);
  const [showRight, setShowRight] = useState(true);
  const [showLeft, setShowLeft] = useState(true);
  const [help, setHelp] = useState(false);
  const autoReview = useRef(false);
  const reviewRef = useRef<(id: string) => void>(() => {});
  const [shareOpen, setShareOpen] = useState(false);
  const [panels, setPanels] = useState<Record<PanelId, boolean>>(() => Object.fromEntries(PANELS.map((p) => [p.id, true])) as Record<PanelId, boolean>);
  useEffect(() => {
    const t = setTimeout(() => setPanels(readPanels()), 0);
    return () => clearTimeout(t);
  }, []);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("quick");
  useEffect(() => {
    const q = search.trim();
    if (q.length < 2) {
      setHits(null);
      return;
    }
    const timer = setTimeout(() => {
      // Project view searches every project; the day view searches the current one.
      searchSessions(q, sidebarView === "project" ? undefined : projectId === ALL ? undefined : projectId)
        .then((r) => setHits(r.results))
        .catch(() => setHits([]));
    }, 250);
    return () => clearTimeout(timer);
  }, [search, sidebarView, projectId]);
  const [pubVersion, setPubVersion] = useState(0);
  const saved = useSavedPrompts();
  const [hello, setHello] = useState("Hello");
  useEffect(() => {
    const t = setTimeout(() => setHello(greeting()), 0);
    return () => clearTimeout(t);
  }, []);
  const [previewPath, setPreviewPath] = useState<string | null>(null);
  const [detail, setDetail] = useState<{ path: string; name: string } | null>(null);  // the result file whose versions, provenance and comments are open
  const [detailFile, setDetailFile] = useState<Artifact | null>(null);  // the result file whose versions, provenance and comments are open
  const [slashIndex, setSlashIndex] = useState(0);
  const [recall, setRecall] = useState<number | null>(null);
  const [driveVersion, setDriveVersion] = useState(0);
  const [dropping, setDropping] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const unsub = useRef<(() => void) | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  // the task running in the conversation on screen; other conversations may be running in the background
  const liveId = useMemo(() => turns.find((t) => t.status === "running")?.id ?? null, [turns]);
  const running = liveId !== null;

  useEffect(() => {
    if (!running) return;
    const t0 = Date.now();
    const tick = setInterval(() => setElapsed(Math.floor((Date.now() - t0) / 1000)), 1000);
    const first = setTimeout(() => setElapsed(0), 0);
    return () => {
      clearInterval(tick);
      clearTimeout(first);
    };
  }, [running]);

  useEffect(() => {
    const t = setTimeout(() => {
      try {
        setShowRight(localStorage.getItem("showRight") !== "0");
        setShowLeft(localStorage.getItem("showLeft") !== "0");
      } catch {}
    }, 0);
    return () => clearTimeout(t);
  }, []);
  const toggleRight = () =>
    setShowRight((v) => {
      try {
        localStorage.setItem("showRight", v ? "0" : "1");
      } catch {}
      return !v;
    });

  useEffect(() => {
    const open = () => setHelp(true);
    window.addEventListener(SHORTCUTS_EVENT, open);
    return () => window.removeEventListener(SHORTCUTS_EVENT, open);
  }, []);

  // Another page (skills, resources, pipelines) may have left a question for the input.
  useEffect(() => {
    const t = setTimeout(() => {
      const text = takePrefill();
      if (text) {
        setPrompt(text);
        input.current?.focus();
      }
    }, 0);
    return () => clearTimeout(t);
  }, []);

  const toggleLeft = () =>
    setShowLeft((v) => {
      try {
        localStorage.setItem("showLeft", v ? "0" : "1");
      } catch {}
      return !v;
    });

  const refreshProjects = useCallback(async () => {
    try {
      setProjects(await listProjects());
    } catch {}
  }, []);

  useEffect(() => {
    const t = setTimeout(() => {
      try {
        setProjectId(localStorage.getItem("project") ?? "quick");
      } catch {}
      refreshProjects();
    }, 0);
    return () => clearTimeout(t);
  }, [refreshProjects]);

  // A remembered project can be gone (deleted elsewhere): fall back to the default instead of showing nothing.
  useEffect(() => {
    if (!projects.length || projectId === ALL || projects.some((p) => p.id === projectId)) return;
    const t = setTimeout(() => {
      setProjectId("quick");
      try {
        localStorage.setItem("project", "quick");
      } catch {}
    }, 0);
    return () => clearTimeout(t);
  }, [projects, projectId]);

  const selectProject = (id: string) => {
    setProjectId(id);
    try {
      localStorage.setItem("project", id);
    } catch {}
  };

  const refreshList = useCallback(async () => {
    try {
      setConvs(await listConversations());
    } catch {}
  }, []);

  useEffect(() => {
    let alive = true;
    const poll = async () => {
      try {
        const h = await getHealth();
        if (alive) {
          setHealth(h);
          setOffline(false);
        }
      } catch {
        if (alive) setOffline(true);
      }
    };
    const init = async () => {
      await poll();
      await refreshList();
    };
    init();
    const t = setInterval(poll, 5000);
    const t2 = setInterval(() => refreshList(), 4000);
    return () => {
      alive = false;
      clearInterval(t);
      clearInterval(t2);
    };
  }, [refreshList]);

  useEffect(() => {
    // Read after mount (not during render) so server and client markup agree.
    const t = setTimeout(() => {
      try {
        const saved = localStorage.getItem("taskMode");
        setMode(isTaskMode(saved) ? saved : localStorage.getItem("planMode") === "1" ? "plan" : "ask");  // the old plan switch carries over
      } catch {}
    }, 0);
    return () => clearTimeout(t);
  }, []);

  // Follow new output only while the reader is already at the bottom; never yank them back from older content.
  const scroller = useRef<HTMLDivElement>(null);
  const stick = useRef(true);
  const onScroll = () => {
    const el = scroller.current;
    if (el) stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 120;
  };
  const lastLen = turns.reduce((n, t) => n + t.events.length, 0);
  useEffect(() => {
    if (stick.current) bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [lastLen, turns.length]);
  useEffect(() => () => unsub.current?.(), []);

  const patchTurn = useCallback((taskId: string, fn: (t: TaskRecord) => TaskRecord) => {
    setTurns((prev) => prev.map((t) => (t.id === taskId ? fn(t) : t)));
  }, []);

  const addSuggestions = useCallback(
    async (taskId: string) => {
      try {
        const ev = await suggestTask(taskId);
        patchTurn(taskId, (t) => ({ ...t, events: [...t.events, ev] }));
      } catch {}
    },
    [patchTurn],
  );

  /** Follow a running task's events from event number `from` (what is already on screen). Leaving the conversation only stops watching. */
  const attach = useCallback(
    (id: string, from: number, answeredAlready: boolean) => {
      unsub.current?.();
      let answered = answeredAlready;
      unsub.current = subscribe(
        id,
        (ev) => {
          if (ev.type === "draft") {
            setChecking(false);
            setLiveDraft(ev.text);
            return;
          }
          if (ev.type === "notice" && ev.check) {
            setChecking(true);
            patchTurn(id, (t) => ({ ...t, events: [...t.events, ev] }));
            return;
          }
          setChecking(false);
          setLiveDraft("");
          if (ev.type === "answer") answered = true;
          patchTurn(id, (t) => ({ ...t, events: [...t.events, ev] }));
          if (ev.type === "done" || ev.type === "error" || ev.type === "cancelled") {
            patchTurn(id, (t) => ({ ...t, status: ev.type }));
            refreshList();
            if (ev.type === "done" && answered) {
              addSuggestions(id);
              if (autoReview.current) reviewRef.current(id);
            }
          }
        },
        () => {
          patchTurn(id, (t) => ({ ...t, status: "interrupted" }));
          setFormError(tr("Connection to the backend was lost. Check that the service is still running."));
        },
        from,
      );
    },
    [patchTurn, refreshList, addSuggestions],
  );

  const startTask = useCallback(
    async (raw: string, approval?: Approval, taskMode: TaskMode = mode) => {
      const text = raw.trim();
      if (!text || running) return;
      setFormError(null);
      setDraft(null);
      try {
        // Only mentions whose "@label" is still in the text count; deleting the text drops the pick.
        const used = picked.filter((m) => text.includes(`@${m.label}`)).map((m) => ({ kind: m.kind, id: m.id }));
        const { id, conversation_id } = await createTask(text, activeId, approval, used, activeId || projectId === ALL ? undefined : projectId, taskMode);
        setPicked([]);
        setActiveId(conversation_id);
        setPrompt("");
        setLiveDraft("");
        stick.current = true;
        setTurns((prev) => [...prev, { id, prompt: text, created: Date.now() / 1000, status: "running", events: [] }]);
        attach(id, 0, false);
        refreshList();
      } catch (e) {
        setFormError(e instanceof Error ? e.message : String(e));
      }
    },
    [running, activeId, picked, attach, refreshList, projectId, mode],
  );

  /** Typed questions go through plan drafting when it is on; simple questions skip it automatically. */
  const submit = useCallback(
    async (raw: string) => {
      const text = raw.trim();
      if (!text || running || drafting) return;
      if (mode === "auto") return startTask(text);  // only the fully automatic mode skips the plan for human approval
      setFormError(null);
      setDrafting(true);
      try {
        const d = await draftPlan(text, activeId);
        if (d.simple && d.questions.length === 0) {
          setDrafting(false);
          return startTask(text);
        }
        setPrompt("");
        setDraft({ prompt: text, questions: d.questions, plan: d.plan });
      } catch (e) {
        setFormError(tr("Plan drafting failed, so it ran directly: {error}", { error: e instanceof Error ? e.message : String(e) }));
        setDrafting(false);
        return startTask(text);
      }
      setDrafting(false);
    },
    [running, drafting, mode, activeId, startTask],
  );

  const setTaskMode = (m: TaskMode) => {
    setMode(m);
    try {
      localStorage.setItem("taskMode", m);
    } catch {}
  };
  /** The slash command /plan: switch between the plan mode and the ask mode. */
  const togglePlanMode = () => setTaskMode(mode === "plan" ? "ask" : "plan");

  const openConversation = async (id: string) => {
    if (id === activeId) return;
    setFormError(null);
    try {
      const c = await getConversation(id);
      unsub.current?.();
      setLiveDraft("");
      setActiveId(id);
      setTurns(c.tasks);
      setDrawer(null);
      stick.current = true;
      // a task still running there: keep following it from where the stored events end
      const r = c.tasks.find((t) => t.status === "running");
      if (r) attach(r.id, r.events.length, r.events.some((e) => e.type === "answer"));
    } catch (e) {
      setFormError(e instanceof Error ? e.message : String(e));
    }
  };

  // A link from a project page ("/?open=<session id>") opens that session, then the address is tidied.
  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get("open");
    if (!id) return;
    openConversation(id);
    window.history.replaceState(null, "", "/");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const newChat = () => {
    unsub.current?.();
    setLiveDraft("");
    setActiveId(null);
    setTurns([]);
    setFormError(null);
    setDrawer(null);
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mod = e.ctrlKey || e.metaKey;
      if (mod && e.key.toLowerCase() === "k") {
        e.preventDefault();
        newChat();
        input.current?.focus();
      } else if (mod && e.key.toLowerCase() === "b") {
        e.preventDefault();
        toggleLeft();
      } else if (mod && e.key === "\\") {
        e.preventDefault();
        toggleRight();
      } else if (!mod && !isTyping(e.target)) {
        if (e.key === "/") {
          e.preventDefault();
          input.current?.focus();
        } else if (e.key === "?") {
          setHelp(true);
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const removeConversation = async (c: ConversationSummary) => {
    if (!window.confirm(tr("Delete “{title}” and all its records?", { title: c.title }))) return;
    try {
      await deleteConversation(c.id);
      if (c.id === activeId) newChat();
      refreshList();
    } catch (e) {
      setFormError(e instanceof Error ? e.message : String(e));
    }
  };

  const forkFrom = (text: string) => {
    if (running) return;
    newChat();
    const brief = text.replace(/\s+/g, " ").slice(0, 300);
    setPrompt(`${tr("Continuing from the last task's conclusions: {brief}", { brief })}${text.length > 300 ? "…" : ""}\n\n${tr("My new question:")}`);
    setTimeout(() => input.current?.focus(), 0);
  };

  const review = async (taskId: string) => {
    setReviewing(taskId);
    try {
      const ev = await reviewTask(taskId);
      patchTurn(taskId, (t) => ({ ...t, events: [...t.events, ev] }));
    } catch (e) {
      setFormError(e instanceof Error ? e.message : String(e));
    } finally {
      setReviewing(null);
    }
  };

  useEffect(() => {
    reviewRef.current = review;
  });
  useEffect(() => {
    let alive = true;
    getPrefs()
      .then((v) => {
        if (alive) autoReview.current = v.prefs.auto_review;
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  const voteOf = (t: TaskRecord) => {
    for (let i = t.events.length - 1; i >= 0; i--) {
      const e = t.events[i];
      if (e.type === "feedback") return e.vote;
    }
    return null;
  };
  const vote = async (taskId: string, v: "up" | "down" | null) => {
    try {
      const ev = await sendFeedback(taskId, v);
      patchTurn(taskId, (t) => ({ ...t, events: [...t.events, ev] }));
    } catch {}
  };

  const allEvents = useMemo(() => turns.flatMap((t) => t.events), [turns]);
  const lastTurnEvents = useMemo(() => (turns.length ? turns[turns.length - 1].events : []), [turns]);
  const plan = useMemo(() => {
    for (let i = lastTurnEvents.length - 1; i >= 0; i--) {
      const e = lastTurnEvents[i];
      if (e.type === "plan") return e.steps;
    }
    return null;
  }, [lastTurnEvents]);
  const toolsEvent = useMemo(() => {
    // the loop reports what it has used so far after each step: the latest report is the one to show
    for (let i = lastTurnEvents.length - 1; i >= 0; i--) {
      const e = lastTurnEvents[i];
      if (e.type === "tools") return e;
    }
    return null;
  }, [lastTurnEvents]);
  const tools = toolsEvent ? toolsEvent.tools : null;
  const knowHow = toolsEvent?.know_how ?? [];
  const artifacts = useMemo(() => {
    const seen = new Map<string, Artifact>();
    for (const e of allEvents) if (e.type === "observation") for (const a of e.artifacts ?? []) seen.set(a.path, a);
    return [...seen.values()];
  }, [allEvents]);
  const ledger = useMemo(() => buildLedger(allEvents), [allEvents]);
  const lastStatus = useMemo(() => {
    for (let i = lastTurnEvents.length - 1; i >= 0; i--) {
      const e = lastTurnEvents[i];
      if (e.type === "status") return e.state;
    }
    return "starting";
  }, [lastTurnEvents]);

  const shownConvs = useMemo(
    () => (projectId === ALL ? convs : convs.filter((c) => (c.project_id ?? "quick") === projectId)),
    [convs, projectId],
  );
  const activeConv = convs.find((c) => c.id === activeId) ?? null;
  const lastTurn = turns.length ? turns[turns.length - 1] : null;
  const shownSeconds = useMemo(() => {
    if (running) return elapsed;
    const stamps = (lastTurn?.events ?? []).map((e) => (e as { ts?: number }).ts).filter((t): t is number => typeof t === "number");
    return stamps.length > 1 ? Math.round(stamps[stamps.length - 1] - stamps[0]) : 0;
  }, [running, elapsed, lastTurn]);
  const headStatus = running ? "running" : lastTurn?.status ?? null;

  const ready = !!health?.agent_ready && !offline && !health?.setup;
  const connection = offline
    ? { dot: "bg-warn", text: t("Backend not connected") }
    : !health
      ? { dot: "bg-soft", text: t("Connecting…") }
      : health.setup
        ? { dot: "bg-warn", text: t(health.setup) }
        : health.agent_error
        ? { dot: "bg-warn", text: t("Agent failed to load: {error}", { error: health.agent_error }) }
        : !health.agent_ready
          ? { dot: "bg-soft pulse", text: t("Agent loading…") }
          : health.busy
            ? { dot: "bg-accent pulse", text: t("Running") }
            : { dot: "bg-accent", text: t("Ready") };


  /** Which step produced each result file: the last observation that listed it. */
  const sourceOf = useMemo(() => {
    const m = new Map<string, string>();
    for (const t of turns) for (const e of t.events) if (e.type === "observation") for (const a of e.artifacts ?? []) m.set(a.path, `ev-${t.id}-${e.seq}`);
    return m;
  }, [turns]);

  const viewSource = (a: Artifact) => {
    const el = document.getElementById(sourceOf.get(a.path) ?? "");
    if (!el) return;
    // open the folded working trace around the step, then scroll to it
    for (let n: HTMLElement | null = el; n; n = n.parentElement) if (n instanceof HTMLDetailsElement) n.open = true;
    el.querySelector("details")?.setAttribute("open", "");
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    el.classList.add("flash");
    setTimeout(() => el.classList.remove("flash"), 1800);
  };

  const reloadConversation = async () => {
    if (!activeId || running) return;
    try {
      const c = await getConversation(activeId);
      setTurns(c.tasks);
      refreshList();
    } catch (e) {
      setFormError(e instanceof Error ? e.message : String(e));
    }
  };

  const slashQ = slashQuery(prompt);
  const slashItems = useMemo(() => (slashQ === null ? [] : filterCommands(slashQ)), [slashQ]);
  const history = useMemo(() => promptHistory(turns.map((t) => t.prompt)), [turns]);

  const runCommand = (c: SlashCommand) => {
    setPrompt("");
    setSlashIndex(0);
    if (c.id === "plan") togglePlanMode();
    else if (c.id === "new") newChat();
    else if (c.id === "layout") toggleRight();
    else if (c.id === "help") setHelp(true);
    else if (c.id === "review") {
      const last = [...turns].reverse().find((t) => t.events.some((e) => e.type === "answer"));
      if (last && !running) review(last.id);
      else setFormError(tr("There is no answer to review yet"));
    }
  };

  /** Files dropped or pasted into the composer go to the cloud drive and are cited in the question. */
  const attachFiles = async (files: FileList | File[]) => {
    const list = Array.from(files);
    if (!list.length) return;
    setFormError(null);
    for (const f of list) {
      try {
        const up = await uploadFile(f);
        setPicked((p) => (p.some((x) => x.kind === "file" && x.id === up.path) ? p : [...p, { kind: "file", id: up.path, label: up.name, hint: "" }]));
        setPrompt((t) => `${t}${t && !t.endsWith(" ") ? " " : ""}@${up.name} `);
      } catch (e) {
        setFormError(`${f.name}：${e instanceof Error ? e.message : String(e)}`);
      }
    }
    setDriveVersion((v) => v + 1);
    input.current?.focus();
  };

  useEffect(() => {
    const el = input.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 220)}px`;
  }, [prompt]);

  return (
    <PreviewContext.Provider value={(a) => setPreviewPath(a.path)}>
    <div
      className={`grid h-full grid-cols-1 ${
        showLeft
          ? showRight
            ? "lg:grid-cols-[240px_minmax(0,1fr)_320px]"
            : "lg:grid-cols-[240px_minmax(0,1fr)]"
          : showRight
            ? "lg:grid-cols-[minmax(0,1fr)_320px]"
            : "lg:grid-cols-1"
      }`}
    >
      {help && <ShortcutHelp onClose={() => setHelp(false)} />}
      {shareOpen && activeConv && (
        <ShareDialog
          title={activeConv.title}
          taskId={lastTurn?.id ?? ""}
          artifacts={artifacts}
          onClose={() => setShareOpen(false)}
          onPublished={() => setPubVersion((v) => v + 1)}
        />
      )}
      {previewPath && artifacts.some((a) => a.path === previewPath) && (
        <FilePreview
          files={artifacts}
          index={Math.max(0, artifacts.findIndex((a) => a.path === previewPath))}
          onIndex={(i) => setPreviewPath(artifacts[i].path)}
          onClose={() => setPreviewPath(null)}
        />
      )}
      {drawer && <div className="fixed inset-0 z-20 bg-black/30 lg:hidden" onClick={() => setDrawer(null)} />}
      {/* Left column: conversation history (a drawer on narrow screens) */}
      <aside
        className={`min-h-0 flex-col border-r border-line bg-panel p-4 lg:static lg:w-auto lg:shadow-none ${showLeft ? "lg:flex" : "lg:hidden"} ${
          drawer === "left" ? "fixed inset-y-0 left-0 z-30 flex w-72 shadow-xl" : "hidden"
        }`}
      >
        <div className="flex items-center gap-2.5 lg:hidden">
          <svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true" className="text-accent">
            <circle cx="14" cy="14" r="12.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
            <path d="M14 5.5c-4.2 2.6-5.6 7.4-3 11.2 1.6 2.3 4.6 3.4 7.2 2.2M14 5.5c3.4 1.6 5 5.2 3.8 8.4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
            <circle cx="14" cy="14" r="1.9" fill="currentColor" />
          </svg>
          <div>
            <h1 className="font-serif text-xl font-semibold leading-tight">Biomni-Desk</h1>
            <p className="text-xs text-soft">{t("Local biomedical agent")}</p>
          </div>
        </div>
        <div className="mt-3">
          <ProjectSwitcher
            projects={projects}
            current={projectId}
            onSelect={selectProject}
            onCreate={async (name) => {
              try {
                const p = await createProject(name);
                await refreshProjects();
                selectProject(p.id);
                return null;
              } catch (e) {
                return e instanceof Error ? e.message : String(e);
              }
            }}
            onRename={async (id, name) => {
              try {
                setProjects(await renameProject(id, name));
                return null;
              } catch (e) {
                return e instanceof Error ? e.message : String(e);
              }
            }}
            onDelete={async (id, mode) => {
              try {
                setProjects(await deleteProject(id, mode ?? "keep"));
                selectProject("quick");
                refreshList();
                return null;
              } catch (e) {
                return e instanceof Error ? e.message : String(e);
              }
            }}
          />
        </div>
        <button
          type="button"
          onClick={newChat}
          title={t("New task (Ctrl K)")}
          className="mt-3 flex items-center justify-center gap-2 rounded-xl bg-accent px-3 py-2 text-sm font-medium text-white shadow-sm disabled:opacity-50 dark:text-black"
        >
          <span aria-hidden="true" className="text-base leading-none">＋</span> {t("New task")}
        </button>
        <div className="mt-3 flex items-center gap-1 text-xs" role="tablist" aria-label={t("Sidebar view")}>
          {(
            [
              ["project", "By project"],
              ["time", "By day"],
            ] as const
          ).map(([v, label]) => (
            <button
              key={v}
              type="button"
              role="tab"
              aria-selected={sidebarView === v}
              onClick={() => {
                setSidebarView(v);
                try {
                  localStorage.setItem("sidebarView", v);
                } catch {}
              }}
              className={`rounded-full border px-2.5 py-0.5 ${sidebarView === v ? "border-accent bg-accent-soft text-accent" : "border-line text-soft hover:border-accent"}`}
            >
              {t(label)}
            </button>
          ))}
        </div>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t("Search history")}
          className="mt-2 rounded-lg border border-line bg-card px-3 py-1.5 text-sm outline-none placeholder:text-soft focus:border-accent"
        />
        <div className="mt-2 min-h-0 flex-1 overflow-y-auto pr-0.5">
          <HistoryList
            convs={sidebarView === "project" ? convs : shownConvs}
            view={sidebarView}
            hits={search.trim().length >= 2 ? hits : null}
            activeProject={projectId}
            onSelectProject={(id) => selectProject(id)}
            onNewInProject={(id) => {
              selectProject(id);
              newChat();
            }}
            activeId={activeId}
            query={search}
            runningId={liveId ? activeId : null}
            onOpen={openConversation}
            onRename={async (c, title) => {
              await renameConversation(c.id, title);
              refreshList();
            }}
            onDelete={removeConversation}
            projects={projects}
            onMove={async (c, pid) => {
              try {
                await moveConversation(c.id, pid);
                await Promise.all([refreshList(), refreshProjects()]);
              } catch (e) {
                setFormError(e instanceof Error ? e.message : String(e));
              }
            }}
          />
        </div>
        <Drive
          version={driveVersion}
          publishedVersion={pubVersion}
          onPick={(f) => {
            const m: Mention = { kind: "file", id: f.path, label: f.name, hint: "" };
            setPicked((p) => (p.some((x) => x.kind === m.kind && x.id === m.id) ? p : [...p, m]));
            setPrompt((t) => `${t}${t && !t.endsWith(" ") ? " " : ""}@${f.name} `);
            input.current?.focus();
          }}
        />
        <div
          className="mt-3 flex items-center gap-2 border-t border-line pt-3 text-xs text-soft"
          title={`${connection.text}${health ? `\n${t("Model: {model}", { model: health.model })}\n${health.commercial_mode ? t("Commercial mode") : t("Academic mode (all datasets)")}` : ""}`}
        >
          <span className={`inline-block h-2 w-2 shrink-0 rounded-full ${connection.dot}`} />
          <span className="min-w-0 flex-1 truncate">
            {connection.text}
            {health && connection.text === t("Ready") ? ` · ${health.model}` : ""}
          </span>
        </div>
      </aside>

      {/* Middle column: conversation */}
      <main className="flex min-h-0 flex-col">
        <div className="flex items-center justify-between border-b border-line bg-panel px-3 py-2 lg:hidden">
          <button type="button" onClick={() => setDrawer("left")} className="rounded-md border border-line px-2.5 py-1 text-sm">
            ☰ {t("History")}
          </button>
          <span className="flex items-center gap-2 font-serif font-semibold">
            Biomni-Desk
            {(running || shownSeconds > 0) && (
              <span className={`font-sans text-xs font-normal tabular-nums ${running ? "text-accent" : "text-soft"}`}>{clock(shownSeconds)}</span>
            )}
          </span>
          <button type="button" onClick={() => setDrawer("right")} className="rounded-md border border-line px-2.5 py-1 text-sm">
            {t("Plan & results")}
          </button>
        </div>
        <div className="hidden items-center gap-2 border-b border-line px-5 py-2.5 text-sm lg:flex">
          <button
            type="button"
            onClick={toggleLeft}
            title={t("Show / hide left column (Ctrl B)")}
            aria-label={t("Show or hide left column")}
            aria-pressed={showLeft}
            className="rounded-md px-1.5 py-0.5 text-soft hover:bg-card hover:text-accent"
          >
            ☰
          </button>
          <span className="shrink-0 whitespace-nowrap text-soft">{t(projects.find((p) => p.id === (activeConv?.project_id ?? "quick"))?.name ?? "Quick task")}</span>
          <span className="shrink-0 text-soft">/</span>
          <span className="min-w-0 truncate font-medium">{activeConv?.title ?? t("New task")}</span>
          <span className="ml-auto flex shrink-0 items-center gap-3">
            {activeId && activeConv && (
              <>
                <TransferMenu
                  projects={projects}
                  current={activeConv.project_id ?? "quick"}
                  onMove={async (pid) => {
                    try {
                      await moveConversation(activeId, pid);
                      await Promise.all([refreshList(), refreshProjects()]);
                    } catch (e) {
                      setFormError(e instanceof Error ? e.message : String(e));
                    }
                  }}
                  onCreateAndMove={async (name) => {
                    try {
                      const p = await createProject(name);
                      await moveConversation(activeId, p.id);
                      await Promise.all([refreshList(), refreshProjects()]);
                    } catch (e) {
                      setFormError(e instanceof Error ? e.message : String(e));
                    }
                  }}
                />
                {activeId && (
                  <a
                    href={`/notebook?c=${encodeURIComponent(activeId)}`}
                    title={t("Open this session as a notebook: questions, code, output and answers in order")}
                    className="rounded-md border border-line px-2 py-0.5 text-xs text-soft hover:border-accent"
                  >
                    {t("Notebook")}
                  </a>
                )}
                <button
                  type="button"
                  disabled={running}
                  onClick={() => setShareOpen(true)}
                  title={t("Turn this conversation into a standalone web page")}
                  className="rounded-md border border-line px-2 py-0.5 text-xs text-soft hover:border-accent disabled:opacity-50"
                >
                  {t("Share")}
                </button>
              </>
            )}
            {headStatus && (
              <span
                className={`rounded-full px-2 py-0.5 text-xs ${
                  headStatus === "running"
                    ? "bg-accent-soft text-accent"
                    : headStatus === "done"
                      ? "text-soft"
                      : "bg-codebg text-warn"
                }`}
              >
                {{ running: t("Running"), done: t("Done"), error: t("Error"), cancelled: t("Stopped"), interrupted: t("Interrupted") }[headStatus] ?? headStatus}
              </span>
            )}
            {(running || shownSeconds > 0) && (
              <span className={`tabular-nums ${running ? "text-accent" : "text-soft"}`} title={running ? t("Elapsed") : t("Time for this task")}>
                {clock(shownSeconds)}
              </span>
            )}
            <button
              type="button"
              onClick={() => setHelp(true)}
              title={t("Keyboard shortcuts (?)")}
              aria-label={t("Keyboard shortcuts")}
              className="rounded-md border border-line px-2 py-0.5 text-xs text-soft hover:border-accent"
            >
              ?
            </button>
            <LayoutMenu value={panels} onChange={setPanels} />
          </span>
        </div>
        <div ref={scroller} onScroll={onScroll} className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden px-5 py-6">
          <div className="mx-auto max-w-3xl space-y-3" aria-label={t("Conversation")} role="log">
            {turns.length === 0 && (
              <div className="pt-12 text-center">
                <svg width="44" height="44" viewBox="0 0 28 28" aria-hidden="true" className="mx-auto mb-5 text-accent">
                  <circle cx="14" cy="14" r="12.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
                  <path d="M14 5.5c-4.2 2.6-5.6 7.4-3 11.2 1.6 2.3 4.6 3.4 7.2 2.2M14 5.5c3.4 1.6 5 5.2 3.8 8.4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                  <circle cx="14" cy="14" r="1.9" fill="currentColor" />
                </svg>
                <h2 className="font-serif text-4xl font-semibold tracking-tight">{t("{greeting}, what would you like to research today?", { greeting: t(hello) })}</h2>
                <p className="mx-auto mt-3 max-w-md text-[15px] text-soft">{t("The agent first lists a plan, then queries databases and runs code step by step, and finally gives an answer with sources.")}</p>
                {shownConvs.length > 0 && (
                  <section className="mx-auto mt-8 w-full max-w-3xl text-left">
                    <h3 className="mb-2 text-xs font-medium tracking-wider text-soft">{t("Recent tasks")}</h3>
                    <ul className="grid gap-2 sm:grid-cols-3">
                      {shownConvs.slice(0, 3).map((c) => (
                        <li key={c.id}>
                          <button
                            type="button"
                            onClick={() => openConversation(c.id)}
                            className="w-full rounded-xl border border-line bg-card p-3 text-left hover:border-accent"
                          >
                            <span className="line-clamp-2 text-sm">{c.title}</span>
                            <span className="mt-1 block text-xs text-soft">{relativeTime(c.updated)}</span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </section>
                )}
                <SavedPrompts
                  items={saved.items}
                  onPick={(q) => {
                    setPrompt(q);
                    input.current?.focus();
                  }}
                  onRemove={saved.remove}
                />
                <Gallery onPick={(q) => { setPrompt(q); input.current?.focus(); }} />
              </div>
            )}
            {turns.map((turn, ti) => {
              const isLast = ti === turns.length - 1;
              const hasReview = turn.events.some((e) => e.type === "review");
              const sugg = turn.events.find((e) => e.type === "suggestions");
              const ask = turn.events.find((e) => e.type === "ask");
              const turnLedger = buildLedger(turn.events); // this answer's own sources, not the whole conversation's
              const live = turn.id === liveId;
              return (
                <div key={turn.id} className="space-y-3" data-turn>
                  <div className="group ml-auto max-w-[85%]">
                    <div data-prompt className="rounded-2xl rounded-br-sm bg-accent-soft px-4 py-2.5 whitespace-pre-wrap select-text">
                      {turn.prompt}
                    </div>
                    {/* the question can be copied, or put back into the input box to ask again or edit it */}
                    <div className="mt-0.5 flex justify-end gap-3 opacity-0 transition-opacity focus-within:opacity-100 group-hover:opacity-100">
                      <CopyButton text={turn.prompt} label={t("Copy question")} />
                      <button
                        type="button"
                        className="text-xs text-soft hover:text-ink"
                        onClick={() => {
                          setPrompt(turn.prompt);
                          input.current?.focus();
                        }}
                      >
                        {t("Put back in input")}
                      </button>
                    </div>
                  </div>
                  {groupEvents(turn.events.filter((e) => !HIDDEN.has(e.type))).map((g) => {
                    const items = g.items.map((ev) => (
                      <div key={ev.seq} id={`ev-${turn.id}-${ev.seq}`}>
                      <EventView
                        ev={ev}
                        onReview={ev.type === "answer" && !live ? () => review(turn.id) : undefined}
                        onSaveSkill={ev.type === "answer" && !live ? () => setSkillFor(turn.id) : undefined}
                        onRevise={ev.type === "review" && !live && isLast ? () => startTask(REVISE_PROMPT) : undefined}
                        reviewing={reviewing === turn.id}
                        hasReview={hasReview}
                        ledger={turnLedger}
                        turnId={turn.id}
                        onFork={forkFrom}
                        vote={voteOf(turn)}
                        onVote={(v) => vote(turn.id, v)}
                        callInfo={ev.type === "answer" ? callSummary(turn.events) : undefined}
                        media={ev.type === "answer" ? mediaOf(turn.events) : undefined}
                      />
                      </div>
                    ));
                    return g.process ? (
                      <ProcessGroup key={g.items[0].seq} items={g.items} live={live}>
                        <StepCards items={g.items} turnId={turn.id} live={live} />
                      </ProcessGroup>
                    ) : (
                      items
                    );
                  })}
                  {skillFor === turn.id && (
                    <SkillDraftDialog
                      taskId={turn.id}
                      onClose={() => setSkillFor(null)}
                      onSaved={(id) => {
                        setSkillFor(null);
                        setSkillNote(`${turn.id}:${id}`);
                      }}
                    />
                  )}
                  {skillNote?.startsWith(`${turn.id}:`) && (
                    <p role="status" className="mt-2 text-xs text-accent">
                      {t("Saved to your skills: {name}", { name: skillNote.slice(turn.id.length + 1) })}
                    </p>
                  )}
                  {live && liveDraft && <LiveDraft text={liveDraft} />}
                  {live && (checking || !(liveDraft.includes("<solution>") && liveDraft.split("<solution>")[1].trim())) && (
                    <p role="status" aria-live="polite" className="flex items-center gap-2 text-sm text-soft">
                      <span className="pulse inline-block h-2 w-2 rounded-full bg-accent" />
                      {checking
                        ? liveDraft
                          ? t("Checking sources and revising the answer; the version above is the one before revision…")
                          : t("Checking the sources and specific facts in the answer; the answer will be given after the check…")
                        : t(STATE_LABEL[lastStatus] ?? "Working…")}
                    </p>
                  )}
                  {turn.status === "interrupted" && <p className="text-sm text-warn">{t("This task was interrupted when the service restarted.")}</p>}
                  {isLast && !live && sugg && sugg.type === "suggestions" && sugg.items.length > 0 && (
                    <FollowUps items={sugg.items} onPick={(q) => startTask(q)} />
                  )}
                  {isLast && !live && ask && ask.type === "ask" && ask.options.length > 0 && (
                    <AskChoices options={ask.options} onPick={(q) => startTask(q)} />
                  )}
                  {(() => {
                    // A database permission the task is waiting on: shown only while it is the newest thing the task has done.
                    const perm = [...turn.events].reverse().find((e) => e.type === "permission");
                    if (!perm || perm.type !== "permission") return null;
                    const after = turn.events.slice(turn.events.indexOf(perm) + 1);
                    if (after.some((e) => ["observation", "code", "answer", "tool", "error", "cancelled", "done"].includes(e.type))) return null;  // answered: work went on
                    return <PermissionCard taskId={turn.id} request={perm} />;
                  })()}
                </div>
              );
            })}
            {drafting && (
              <p className="flex items-center gap-2 text-sm text-soft">
                <span className="pulse inline-block h-2 w-2 rounded-full bg-accent" />
                {t("Drafting a plan…")}
              </p>
            )}
            {draft && (
              <>
                <div className="ml-auto max-w-[85%] rounded-2xl rounded-br-sm bg-accent-soft px-4 py-2.5 whitespace-pre-wrap">
                  {draft.prompt}
                </div>
                <PlanDraft
                  draft={draft}
                  onApprove={(a) => startTask(draft.prompt, a, planMode ? "plan" : "ask")}
                  onSkip={() => startTask(draft.prompt, undefined, planMode ? "plan" : "ask")}
                  onCancel={() => {
                    setPrompt(draft.prompt);
                    setDraft(null);
                  }}
                />
              </>
            )}
            <div ref={bottom} />
          </div>
        </div>

        <div className="border-t border-line bg-panel px-5 py-4">
          <div className="mx-auto max-w-3xl">
            <Tips />
            {formError && <p className="mb-2 text-sm text-warn">{formError}</p>}
            {picked.length > 0 && (
              <div className="mb-2 flex flex-wrap gap-1.5">
                {picked.map((m) => (
                  <span key={`${m.kind}:${m.id}`} className="inline-flex items-center gap-1 rounded-full bg-accent-soft px-2.5 py-0.5 text-xs">
                    @{m.label}
                    <button type="button" title={t("Remove")} onClick={() => setPicked((p) => p.filter((x) => x !== m))} className="text-soft hover:text-warn">
                      ✕
                    </button>
                  </span>
                ))}
              </div>
            )}
            <div
              className={`relative rounded-2xl border bg-card p-3 shadow-sm focus-within:border-accent ${dropping ? "border-accent bg-accent-soft" : "border-line"}`}
              onDragOver={(e) => {
                if (e.dataTransfer.types.includes("Files")) {
                  e.preventDefault();
                  setDropping(true);
                }
              }}
              onDragLeave={() => setDropping(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDropping(false);
                attachFiles(e.dataTransfer.files);
              }}
            >
              {dropping && <p className="pointer-events-none absolute inset-0 z-10 grid place-items-center text-sm text-accent">{t("Release to upload to the drive and cite it")}</p>}
              {slashItems.length > 0 && !menu && <SlashMenu items={slashItems} index={Math.min(slashIndex, slashItems.length - 1)} onPick={runCommand} />}
              {menu && (
                <MentionMenu
                  query={menu.query}
                  trigger={menu.trigger}
                  onClose={() => setMenu(null)}
                  onPick={(m) => {
                    const caret = input.current?.selectionStart ?? prompt.length;
                    const sign = m.kind === "session" ? "#" : menu.trigger === "/" ? "/" : "@";  // what the user typed stays readable in the message
                    const next = `${prompt.slice(0, menu.start)}${sign}${m.label} ${prompt.slice(caret)}`;
                    setPrompt(next);
                    setPicked((p) => (p.some((x) => x.kind === m.kind && x.id === m.id) ? p : [...p, m]));
                    setMenu(null);
                    input.current?.focus();
                  }}
                />
              )}
              <textarea
                ref={input}
                value={prompt}
                onChange={(e) => {
                  setPrompt(e.target.value);
                  setRecall(null);
                  setSlashIndex(0);
                  setMenu(activeTrigger(e.target.value, e.target.selectionStart));
                }}
                onPaste={(e) => {
                  if (e.clipboardData.files.length) {
                    e.preventDefault();
                    attachFiles(e.clipboardData.files);
                  }
                }}
                onClick={(e) => setMenu(activeTrigger(prompt, e.currentTarget.selectionStart))}
                onKeyDown={(e) => {
                  if (e.nativeEvent.isComposing) return;
                  if (slashItems.length > 0 && !menu) {
                    const at = Math.min(slashIndex, slashItems.length - 1);
                    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
                      e.preventDefault();
                      setSlashIndex((at + (e.key === "ArrowDown" ? 1 : slashItems.length - 1)) % slashItems.length);
                      return;
                    }
                    if (e.key === "Enter" || e.key === "Tab") {
                      e.preventDefault();
                      runCommand(slashItems[at]);
                      return;
                    }
                    if (e.key === "Escape") {
                      setPrompt("");
                      return;
                    }
                  }
                  // ↑ / ↓ walk through earlier questions while the box is empty or showing a recalled one.
                  if ((e.key === "ArrowUp" || e.key === "ArrowDown") && !menu && history.length && (prompt === "" || recall !== null)) {
                    e.preventDefault();
                    const next = e.key === "ArrowUp" ? Math.min((recall ?? -1) + 1, history.length - 1) : (recall ?? 0) - 1;
                    if (next < 0) {
                      setRecall(null);
                      setPrompt("");
                    } else {
                      setRecall(next);
                      setPrompt(history[next]);
                    }
                    return;
                  }
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    submit(prompt);
                  }
                }}
                rows={2}
                placeholder={
                  ready
                    ? turns.length
                      ? t("Ask a follow-up (Enter to send, @ to cite, / for commands, ↑ for the previous question, drop files here)")
                      : t("Enter a research question (Enter to send, @ to cite, / for commands, drop files here)")
                    : health?.setup ? t("Set up a model in Settings to start asking questions") : t("Agent loading, please wait…")
                }
                className="block min-h-[3.5rem] w-full resize-none bg-transparent px-1 py-1 outline-none placeholder:text-soft"
              />
              <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-2">
                <AttachMenu
                  disabled={running}
                  onFiles={attachFiles}
                  onPickUploaded={(f) => {
                    setPicked((p) => (p.some((x) => x.kind === "file" && x.id === f.path) ? p : [...p, { kind: "file", id: f.path, label: f.name, hint: "" }]));
                    setPrompt((t) => `${t}${t && !t.endsWith(" ") ? " " : ""}@${f.name} `);
                    input.current?.focus();
                  }}
                />
                <button
                  type="button"
                  title={saved.items.includes(prompt.trim()) ? t("Remove this question from favourites") : t("Save this question as a favourite")}
                  aria-pressed={saved.items.includes(prompt.trim())}
                  disabled={!prompt.trim()}
                  onClick={() => saved.toggle(prompt)}
                  className={`grid h-8 w-8 place-items-center rounded-full border border-line text-base leading-none hover:border-accent disabled:opacity-30 ${
                    saved.items.includes(prompt.trim()) ? "text-accent" : "text-soft"
                  }`}
                >
                  {saved.items.includes(prompt.trim()) ? "★" : "☆"}
                </button>
                <ModePicker mode={mode} options={TASK_MODES} disabled={running} onPick={(id) => setTaskMode(id as TaskMode)} />
                <button
                  type="button"
                  disabled={running}
                  title={t("@-mention tools, datasets, packages and skills the agent can use")}
                  onClick={() => {
                    const at = prompt.length;
                    setPrompt((p) => `${p}@`);
                    setMenu({ start: at, query: "", trigger: "@" });
                    input.current?.focus();
                  }}
                  className="rounded-full border border-accent/60 bg-accent-soft px-3 py-1 text-xs font-medium text-accent hover:border-accent disabled:opacity-40"
                >
                  {t("@ Resources & skills")}
                </button>
                <div className="ml-auto flex items-center gap-2">
                  <ModelPicker key={health ? `${health.source}:${health.model}` : "none"} busy={running || !!health?.busy} up />
                  {running ? (
                    <button
                      type="button"
                      onClick={() => liveId && cancelTask(liveId)}
                      title={t("Stop")}
                      className="grid h-9 w-9 place-items-center rounded-full border border-warn text-warn"
                    >
                      ■
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => submit(prompt)}
                      disabled={!prompt.trim() || offline || drafting || !!draft || !!health?.setup}
                      title={t("Send")}
                      className="grid h-9 w-9 place-items-center rounded-full bg-accent text-white disabled:opacity-40 dark:text-black"
                    >
                      ↑
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* Right column: plan / results / sources / tools */}
      <aside
        className={`min-h-0 flex-col gap-6 overflow-y-auto border-l border-line bg-panel p-4 lg:static lg:w-auto lg:shadow-none ${showRight ? "lg:flex" : "lg:hidden"} ${
          drawer === "right" ? "fixed inset-y-0 right-0 z-30 flex w-80 max-w-[90vw] shadow-xl" : "hidden"
        }`}
      >
        {panels.plan && (
        <SideSection id="plan" title={t("To-do")} count={plan?.length}>
          {plan ? (
            <>
              <ProgressBar done={plan.filter((x) => x.status === "done").length} total={plan.length} />
              <PlanView steps={plan} live={running} />
            </>
          ) : (
            <p className="text-sm text-soft">{t("The plan appears here once the agent gives one, and ticks off as it progresses.")}</p>
          )}
        </SideSection>
        )}
        {panels.results && (
        <SideSection id="results" title={t("Results")} count={artifacts.length}>
          <ResultsPanel
            artifacts={artifacts}
            onOpen={(a) => setPreviewPath(a.path)}
            onViewSource={viewSource}
            onDetails={(a) => setDetailFile(a)}
            onRefresh={activeId && !running ? reloadConversation : undefined}
          />
          {detailFile && activeId && (
            <ArtifactDetail conversationId={activeId} path={detailFile.path} name={detailFile.name} onClose={() => setDetailFile(null)} />
          )}
        </SideSection>
        )}
        {panels.sources && (
        <SideSection id="sources" title={t("Sources")} count={ledger.filter((x) => x.reader).length}>
          <SourceList ledger={ledger} />
        </SideSection>
        )}
        {panels.compute && (
        <SideSection id="compute" title={t("Compute")} count={runsOfCount(allEvents)} defaultOpen={false}>
          <ComputePanel events={allEvents} turns={turns} running={running} />
        </SideSection>
        )}
        {panels.notes && (
        <SideSection id="notes" title={t("Notes")} defaultOpen={false}>
          <NotesPanel conversationId={activeId} />
        </SideSection>
        )}
        <SideSection id="skills" title={t("Skills and know-how used")} count={knowHow.length} defaultOpen={false}>
          {toolsEvent ? (
            knowHow.length ? (
              <ul className="space-y-1 text-sm">
                {knowHow.map((k) => (
                  <li key={k}>· {k}</li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-soft">{t("No matching skills this time.")}</p>
            )
          ) : (
            <p className="text-sm text-soft">{t("Shown once the task starts.")}</p>
          )}
        </SideSection>
        <SideSection id="tools" title={t("Tools selected")} count={tools?.length} defaultOpen={false}>
          {tools ? (
            <ul className="flex flex-wrap gap-1.5">
              {tools.map((t) => (
                <li key={t} className="rounded-md bg-codebg px-2 py-0.5 font-mono text-xs">
                  {t}
                </li>
              ))}
              {tools.length === 0 && <li className="text-sm text-soft">{t("No specialised tools selected")}</li>}
            </ul>
          ) : (
            <p className="text-sm text-soft">{t("Shown once the task starts.")}</p>
          )}
        </SideSection>
      </aside>
    </div>
    </PreviewContext.Provider>
  );
}
