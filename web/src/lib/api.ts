import { tr } from "@/lib/i18n";

export const API = process.env.NEXT_PUBLIC_API ?? "http://127.0.0.1:8765";

export type ToolResult = { title: string; url: string; domain: string; snippet: string };
export type PlanStep = { text: string; status: "todo" | "done" | "failed" };
export type Artifact = { name: string; path: string; kind: "image" | "video" | "pdf" | "table" | "html" | "text"; mtime?: number; size?: number };

type Base = { seq: number; ts: number; /** set on the steps a sub-agent made: the id of its "subagent" card */ sub?: string };
export type AgentEvent = Base &
  (
    | { type: "status"; state: "starting" | "retrieving" | "running" }
    | { type: "notice"; text: string; check?: boolean }
    | { type: "tools"; tools: string[]; libraries: string[]; data_lake: string[]; know_how?: string[] }
    | { type: "plan"; steps: PlanStep[] }
    | { type: "reasoning"; text: string }
    | { type: "tool"; tool: string; query?: string; results?: ToolResult[]; text?: string }
    | { type: "code"; language: string; code: string; elapsed?: number }
    | { type: "observation"; text: string; files: string[]; artifacts?: Artifact[]; elapsed?: number }
    | { type: "answer"; text: string; fallback?: boolean; quick?: boolean }
    | { type: "review"; text: string }
    | { type: "feedback"; vote: "up" | "down" | null }
    | { type: "llm"; model: string; effort: string | null; seconds: number; input_tokens: number | null; output_tokens: number | null; reasoning_tokens: number | null }
    | { type: "suggestions"; items: string[] }
    | { type: "ask"; question: string; options: string[] }
    | { type: "permission"; id: string; tool: string; title: string; choices: string[] }
    | { type: "subagent"; id: string; status: "running" | "done" | "failed"; task?: string; steps?: number; answer?: string }
    | { type: "error"; message: string }
    | { type: "cancelled" }
    | { type: "done" }
    | { type: "draft"; text: string }
  );

export type Health = {
  ok: boolean;
  setup?: string | null;
  agent_ready: boolean;
  agent_error: string | null;
  busy: boolean;
  source: string | null;
  model: string;
  tool_retriever: boolean;
  commercial_mode: boolean;
};

export type ConversationSummary = { id: string; title: string; created: number; updated: number; project_id?: string; status?: string | null };
export type TaskRecord = { id: string; prompt: string; created: number; status: string; events: AgentEvent[] };
export type Conversation = ConversationSummary & { tasks: TaskRecord[] };

async function json<T>(r: Response): Promise<T> {
  if (!r.ok) {
    let detail = `HTTP ${r.status}`;
    try {
      detail = (await r.json()).detail ?? detail;
    } catch {}
    throw new Error(detail);
  }
  return r.json();
}

const get = <T,>(path: string) => fetch(`${API}${path}`, { cache: "no-store" }).then((r) => json<T>(r));
const send = <T,>(method: string, path: string, body?: unknown) =>
  fetch(`${API}${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  }).then((r) => json<T>(r));

export const getHealth = () => get<Health>("/api/health");
export const listConversations = () => get<ConversationSummary[]>("/api/conversations");
export const getConversation = (id: string) => get<Conversation>(`/api/conversations/${id}`);
export const deleteConversation = (id: string) => send<{ ok: boolean }>("DELETE", `/api/conversations/${id}`);
export const renameConversation = (id: string, title: string) =>
  send<{ ok: boolean }>("PATCH", `/api/conversations/${id}`, { title });
export type PlanDraftResult = { simple: boolean; questions: string[]; plan: string[] };
export const draftPlan = (prompt: string, conversationId: string | null) =>
  send<PlanDraftResult>("POST", "/api/plan", { prompt, conversation_id: conversationId });
export const createTask = (
  prompt: string,
  conversationId: string | null,
  approval?: { plan: string[]; answers: [string, string][] },
  mentions?: { kind: string; id: string }[],
  projectId?: string,
  mode?: "plan" | "ask" | "auto",
  agentId?: string | null,
) =>
  send<{ id: string; conversation_id: string }>("POST", "/api/tasks", {
    prompt,
    conversation_id: conversationId,
    approval,
    mentions: mentions ?? [],
    project_id: projectId,
    mode: mode ?? "ask",
    agent_id: agentId || null,
  });
export const cancelTask = (id: string) => send<{ ok: boolean }>("POST", `/api/tasks/${id}/cancel`);
export const reviewTask = (id: string) => send<AgentEvent>("POST", `/api/tasks/${id}/review`);
export const suggestTask = (id: string) => send<AgentEvent>("POST", `/api/tasks/${id}/suggest`);
/** A reusable skill drafted from a finished task. It is saved only after the user reviews it (createSkill). */
export const skillDraft = (id: string) =>
  send<{ title: string; description: string; category: string; when_to_use: string; avoid: string; body: string }>("POST", `/api/tasks/${id}/skill-draft`);
export const fileUrl = (path: string) => `${API}/api/files?p=${encodeURIComponent(path)}`;

const TERMINAL = new Set(["done", "error", "cancelled"]);

/** Subscribe to a task's events. EventSource reconnects with Last-Event-ID on its own. */
export function subscribe(
  id: string,
  onEvent: (e: AgentEvent) => void,
  onConnectionLost: () => void,
  from = 0,
): () => void {
  const es = new EventSource(`${API}/api/tasks/${id}/events${from ? `?from=${from}` : ""}`);
  es.onmessage = (m) => {
    const ev = JSON.parse(m.data) as AgentEvent;
    onEvent(ev);
    if (TERMINAL.has(ev.type)) es.close();
  };
  es.onerror = () => {
    if (es.readyState === EventSource.CLOSED) onConnectionLost();
  };
  return () => es.close();
}

export { collectSources, type Source } from "./citations";

export type Skill = {
  id: string;
  source: "builtin" | "mine";
  enabled: boolean;
  title: string;
  description: string;
  category: string;
  when_to_use: string;
  avoid: string;
  uses: string;
  chain: string;
  body: string;
};
export type SkillInput = Partial<Omit<Skill, "source" | "enabled">>;

export const listSkills = () => get<Skill[]>("/api/skills");
export const getSkill = (id: string) => get<Skill>(`/api/skills/${id}`);
export const createSkill = (s: SkillInput) => send<Skill>("POST", "/api/skills", s);
export const updateSkill = (id: string, s: SkillInput) => send<Skill>("PUT", `/api/skills/${id}`, s);
export const deleteSkill = (id: string) => send<{ ok: boolean }>("DELETE", `/api/skills/${id}`);
export const toggleSkill = (id: string, enabled: boolean) =>
  send<{ ok: boolean }>("PATCH", `/api/skills/${id}`, { enabled });
export const importSkill = (url: string) => send<Skill>("POST", "/api/skills/import", { url });

/** The curated community library: skill collections (installable), tools and reference lists (for reference only). */
export type CommunityEntry = {
  id: string;
  kind: "skills" | "tools" | "lists";
  name: string;
  repo: string;
  url: string;
  branch?: string;
  description: string;
  license: string;
  last_changed: string;
  archived: boolean;
  skill_count?: number;
  keywords: string[];
  note: string;
};
export type CommunityFile = { path: string; folder: string; url: string };
export const searchCommunity = (q: string, kind: string) =>
  get<{ checked_on: string; note: string; items: CommunityEntry[] }>(`/api/community?q=${encodeURIComponent(q)}&kind=${encodeURIComponent(kind)}`);
export const communitySkills = (id: string) =>
  get<{ entry: CommunityEntry; files: CommunityFile[]; present: string[] }>(`/api/community/${encodeURIComponent(id)}/skills`);
export const installCommunity = (id: string, paths: string[]) =>
  send<{ results: { path: string; ok: boolean; id?: string; title?: string; error?: string }[]; added: number }>("POST", `/api/community/${encodeURIComponent(id)}/install`, { paths });
export const githubTokenState = () => get<{ set: boolean }>("/api/credentials/github");
export const setGithubToken = (token: string | null) => send<{ set: boolean }>("PUT", "/api/credentials/github", { token });
export type SkillUpdate = { skill_id: string; title: string; current_commit: string | null; latest_commit: string | null; changed: boolean };
export const checkSkillUpdates = () => get<{ updates: SkillUpdate[] }>("/api/skill-updates");
export const applySkillUpdates = (ids: string[]) => send<{ updated: string[] }>("POST", "/api/skill-updates/apply", { ids });

export type Schedule = {
  id: string;
  name: string;
  prompt: string;
  project_id: string;
  schedule: { kind: "every"; minutes: number } | { kind: "daily"; time: string };
  enabled: boolean;
  next_run: number | null;
  last_run: number | null;
  last_task_id: string | null;
  last_conversation_id: string | null;
  last_status: string;
};
export type ScheduleInput = {
  name: string;
  prompt: string;
  project_id?: string | null;
  kind: "every" | "daily";
  minutes?: number | null;
  time?: string | null;
  enabled: boolean;
};
export const listSchedules = () => get<Schedule[]>("/api/schedules");
export const createSchedule = (s: ScheduleInput) => send<Schedule>("POST", "/api/schedules", s);
export const updateSchedule = (id: string, s: ScheduleInput) => send<Schedule>("PUT", `/api/schedules/${id}`, s);
export const deleteSchedule = (id: string) => send<{ ok: boolean }>("DELETE", `/api/schedules/${id}`);
export const runScheduleNow = (id: string) => send<{ id: string; conversation_id: string }>("POST", `/api/schedules/${id}/run`);

export type SettingsValues = {
  source: string | null;
  model: string;
  use_tool_retriever: boolean;
  commercial_mode: boolean;
};
export type SettingsView = { values: SettingsValues; sources: Record<string, string>; custom_ready: boolean };
export const getSettings = () => get<SettingsView>("/api/settings");
export const putSettings = (s: Partial<SettingsValues>) => send<SettingsView>("PUT", "/api/settings", s);

export type Mention = { kind: "skill" | "tool" | "data" | "file" | "session"; id: string; label: string; hint: string };
export const searchMentions = (q: string) => get<Mention[]>(`/api/mentions?q=${encodeURIComponent(q)}`);

export type Cost = "member" | "free" | "paid" | "local";
export type ModelEntry = {
  id: string;
  label: string;
  source: "Codex" | "Custom";
  model: string;
  note: string;
  builtin: boolean;
  cost: Cost;
  hidden?: boolean;
  provider: string;
  provider_name: string;
  /** false: the provider has no usable key yet */
  provider_ready: boolean;
  /** the reasoning efforts this model really accepts (empty: it cannot be adjusted) and the one in use */
  effort_options: string[];
  effort: string | null;
  /** false: no longer on OpenRouter; null: not checked yet */
  available: boolean | null;
  price: { prompt: number; completion: number; context: number } | null;
};
export type ModelsView = {
  models: ModelEntry[];
  active: { id: string | null; source: string | null; model: string; reasoning_effort: string; effort_options: string[] };
  removed: number;
  providers: Provider[];
  custom_ready: boolean;
  efforts: string[];
  /** the models for the helper roles (null: the main model), the reasoning level for each, and the sub-agent and memory settings */
  roles: ModelRoles;
};
/** Which model and level each helper role uses. Null means the main model (or the model's own default level). */
export type ModelRoles = {
  planner_model_id: string | null;
  subagent_model_id: string | null;
  reviewer_model_id: string | null;
  image_model_id: string | null;
  planner_effort: string | null;
  subagent_effort: string | null;
  reviewer_effort: string | null;
  subagent_max: number;
  memory_recall_chars: number;
  memory_auto: boolean;
};
export const getModels = () => get<ModelsView>("/api/models");
/** Only the fields given are changed; a model or level sent as null goes back to the main model's. */
export const setModelRoles = (body: Partial<ModelRoles>) => send<ModelsView>("PUT", "/api/model-roles", body);
export const setActive = (body: { id?: string; reasoning_effort?: string; confirm_paid?: boolean }) => send<ModelsView>("PUT", "/api/active", body);
export const addModel = (m: { model: string; label?: string; note?: string; provider?: string }) =>
  send<ModelsView & { added: ModelEntry }>("POST", "/api/models", m);
export const deleteModel = (id: string) => send<ModelsView>("DELETE", `/api/models/${id}`);
export const testModel = (id: string, confirmPaid = false) =>
  send<{ ok: boolean; seconds: number; reply?: string; error?: string }>("POST", `/api/models/${id}/test?confirm_paid=${confirmPaid}`);

export type ChatGPTStatus = { logged_in: boolean; pending: { user_code: string; verification_url: string } | null; error: string | null };
export const chatgptStatus = () => get<ChatGPTStatus>("/api/chatgpt");
export const chatgptLogin = () => send<ChatGPTStatus>("POST", "/api/chatgpt/login");
export const chatgptLogout = () => send<ChatGPTStatus>("POST", "/api/chatgpt/logout");

export type RefMeta = { kind: "paper" | "web"; title?: string; authors?: string; journal?: string; year?: string; doi?: string; site?: string };
export const resolveRefs = (items: { kind: string; id: string }[]) =>
  send<Record<string, RefMeta>>("POST", "/api/refs/resolve", { items });

export type Upload = Artifact & { mtime?: number; size?: number };
export const listUploads = () => get<Upload[]>("/api/uploads");
export const deleteUpload = (name: string) => send<{ ok: boolean }>("DELETE", `/api/uploads/${encodeURIComponent(name)}`);
export async function uploadFile(file: File): Promise<Upload> {
  const fd = new FormData();
  fd.append("file", file);
  return json<Upload>(await fetch(`${API}/api/uploads`, { method: "POST", body: fd }));
}
export const sendFeedback = (taskId: string, vote: "up" | "down" | null) =>
  send<AgentEvent>("POST", `/api/tasks/${taskId}/feedback`, { vote });
export const downloadUrl = (path: string) => `${API}/api/files?p=${encodeURIComponent(path)}&download=true`;

/** Open a result file with the default program of this computer, or show it in its folder. */
export const openOnHost = (path: string, action: "open" | "folder" = "open") => send<{ ok: boolean }>("POST", "/api/open", { path, action });

export type Project = { id: string; name: string; created: number; default: boolean; count: number };
export const listProjects = () => get<Project[]>("/api/projects");
export const createProject = (name: string) => send<Project>("POST", "/api/projects", { name });
export const renameProject = (id: string, name: string) => send<Project[]>("PATCH", `/api/projects/${id}`, { name });
/** "keep": the sessions move to the quick-task area. "cascade": the project and everything in it is deleted. */
export const deleteProject = (id: string, mode: "keep" | "cascade" = "keep") => send<Project[]>("DELETE", `/api/projects/${id}?mode=${mode}`);
export type ProjectSummary = { sessions: number; tasks: number; published: number; notes: number; files: number; skills: string[]; tools_off: string[] };
export const getProjectSummary = (id: string) => get<ProjectSummary>(`/api/projects/${id}/summary`);
export type SearchHit = { id: string; title: string; updated: number; project_id: string; snippet: string };
export const searchSessions = (q: string, project?: string) =>
  get<{ results: SearchHit[] }>(`/api/search?q=${encodeURIComponent(q)}${project ? `&project=${encodeURIComponent(project)}` : ""}`);
// ---- versions, provenance and comments on result files (per session) ----
export type FileVersion = { version: number; sha256: string; size: number; task_id: string; time: number; reason: string };
export type VersionedFile = { path: string; latest: FileVersion; count: number };
export type Provenance = {
  path: string;
  version: FileVersion;
  task: { id: string; prompt: string; created: number | null };
  messages: { question: string; answer: string };
  code: { title: string; language: string; code: string }[];
  execution_log: { tool: string; time: string; summary: string; result_sha256: string | null; failed: boolean }[];
  environment: { python: string; platform: string; model: string | null; effort: string | null };
  review: string | null;
};
export type Comment = { id: string; path: string; quote: string; text: string; created: number; sent_in_task: string | null; sent_at: number | null };
export const listVersionedFiles = (cid: string) => get<{ files: VersionedFile[] }>(`/api/conversations/${cid}/files`);
export const listVersions = (cid: string, path: string) =>
  get<{ versions: FileVersion[] }>(`/api/conversations/${cid}/versions?path=${encodeURIComponent(path)}`);
export const versionFileUrl = (cid: string, sha256: string, name: string, download = false) =>
  `${API}/api/conversations/${cid}/version-file?sha=${sha256}&name=${encodeURIComponent(name)}${download ? "&download=true" : ""}`;
export const restoreVersion = (cid: string, path: string, version: number) =>
  send<{ version: FileVersion; versions: FileVersion[] }>("POST", `/api/conversations/${cid}/versions/restore`, { path, version });
export const getProvenance = (cid: string, path: string, version: number) =>
  get<Provenance>(`/api/conversations/${cid}/provenance?path=${encodeURIComponent(path)}&version=${version}`);
export type NotebookCell =
  | { kind: "question"; task_id: string; text: string }
  | { kind: "code"; task_id: string; language: string; code: string; output: string; files: string[]; elapsed: number | null }
  | { kind: "tool"; task_id: string; tool: string; query: string }
  | { kind: "answer"; task_id: string; text: string };
export type Notebook = { title: string; environment: { python: string; platform: string }; cells: NotebookCell[] };
export const getNotebook = (cid: string) => get<Notebook>(`/api/conversations/${cid}/notebook`);
export const listComments = (cid: string) => get<{ items: Comment[] }>(`/api/conversations/${cid}/annotations`);
export const addComment = (cid: string, path: string, text: string, quote = "") =>
  send<{ items: Comment[] }>("POST", `/api/conversations/${cid}/annotations`, { path, text, quote });
export const deleteComment = (cid: string, id: string) => send<{ items: Comment[] }>("DELETE", `/api/conversations/${cid}/annotations/${id}`);

export const moveConversation = (id: string, projectId: string) =>
  send<{ ok: boolean }>("PATCH", `/api/conversations/${id}`, { project_id: projectId });

export const getNotes = (id: string) => get<{ text: string }>(`/api/conversations/${id}/notes`);
export const putNotes = (id: string, text: string) => send<{ ok: boolean }>("PUT", `/api/conversations/${id}/notes`, { text });

export type Published = { id: string; title: string; created: number; task_id: string };
export const listPublished = () => get<Published[]>("/api/published");
export const publishResult = (b: { title: string; html: string; task_id?: string }) => send<{ id: string; title: string }>("POST", "/api/published", b);
export const deletePublished = (id: string) => send<{ ok: boolean }>("DELETE", `/api/published/${id}`);
export const publishedUrl = (id: string) => `${API}/api/published/${id}/html`;

export type Runtime = { python: string; platform: string; executable: string; workdir: string; data_path: string; timeout_seconds: number | null; model: string; source: string };
export const getRuntime = () => get<Runtime>("/api/runtime");

/** Several result files as one zip download. */
export async function downloadZip(paths: string[]): Promise<void> {
  const r = await fetch(`${API}/api/files/zip`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ paths }) });
  if (!r.ok) throw new Error(tr("Download failed (HTTP {status})", { status: r.status }));
  const url = URL.createObjectURL(await r.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = "results.zip";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export type Usage = {
  tasks_total: number;
  status: Record<string, number>;
  series: { day: string; tasks: number }[];
  code_runs: number;
  code_seconds: number;
  conversations: number;
};
export const getUsage = () => get<Usage>("/api/usage");

export type ResourceItem = { name: string; description: string; module?: string; status?: string; note?: string };
export type Resources = { ready: boolean; tools: ResourceItem[]; data: ResourceItem[]; libraries: ResourceItem[]; tool_summary?: Record<string, number> };
export const getResources = () => get<Resources>("/api/resources");

export type Profile = { first_name: string; last_name: string; institution: string; position: string; scholar: string; website: string; orcid: string; areas: string[] };
export type Prefs = {
  language: "any" | "python" | "r";
  image_format: "any" | "png" | "svg";
  style: "classic" | "modern";
  appearance: "auto" | "light" | "dark";
  instructions: string[];
  use_last_results: boolean;
  auto_review: boolean;
};
export type PrefsView = { profile: Profile; prefs: Prefs; areas: string[] };
export const getPrefs = () => get<PrefsView>("/api/prefs");

export type Connector = { id: string; title: string; tools: string[]; enabled: boolean };
/** source: you (typed by you), agent (proposed by the agent during a task), auto (suggested after a finished task). */
export type MemoryNote = { id: string; text: string; created: number; status: "approved" | "proposed"; project_id: string | null; category: string; source: "you" | "agent" | "auto" };
export const getConnectors = () => get<{ connectors: Connector[] }>("/api/connectors");
export const setConnector = (id: string, enabled: boolean) => send<{ connectors: Connector[] }>("PUT", `/api/connectors/${id}`, { enabled });
export const getMemoryNotes = () => get<{ items: MemoryNote[] }>("/api/memory-notes");
export const deleteMemoryNote = (id: string) => send<{ items: MemoryNote[] }>("DELETE", `/api/memory-notes/${id}`);
export const addMemoryNote = (text: string, projectId: string | null, category = "General") =>
  send<{ items: MemoryNote[] }>("POST", "/api/memory-notes", { text, project_id: projectId, category });
export const approveMemoryNote = (id: string) => send<{ items: MemoryNote[] }>("POST", `/api/memory-notes/${id}/approve`);
/** The community hub: skills (from the index), tools, databases and software (curated, for reference). */
export type HubItem = {
  id: string;
  kind: "skills" | "tools" | "lists" | "databases" | "software";
  name: string;
  description?: string;
  repo?: string;
  path?: string;
  url?: string;
  source?: string;
  trust: "community" | "trusted" | "reference";
  license?: string;
  archived?: boolean;
  last_changed?: string;
  keywords?: string[];
  note?: string;
  installed?: boolean;
  skill_count?: number;
};
export type HubFinding = { line: number; severity: string; rule: string; text: string };
export const hubSearch = (q: string, kind: string, trust: string) =>
  get<{ items: HubItem[]; count: number; built_on: string; indexed: number; skipped: number; checked_on: string }>(
    `/api/hub/search?q=${encodeURIComponent(q)}&kind=${encodeURIComponent(kind)}&trust=${encodeURIComponent(trust)}`,
  );
export const hubRefresh = () => send<{ started: boolean; status: { state: string; message: string } }>("POST", "/api/hub/refresh");
export const hubStatus = () => get<{ state: string; message: string }>("/api/hub/status");
export const hubInspect = (url: string) => send<{ verdict: string; findings: HubFinding[]; text: string }>("POST", "/api/hub/inspect", { url });
/** Install through the policy. A refusal comes back as a result (not an error) so the findings can be shown. */
export async function hubInstall(url: string, force: boolean): Promise<{ ok: boolean; status: number; body: any }> {
  const r = await fetch(`${API}/api/hub/install`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url, force }) });
  const body = await r.json().catch(() => ({}));
  return { ok: r.ok, status: r.status, body };
}

/** What a project's finished tasks did (kept automatically): the question and the start of the answer. */
export type WorkItem = { id: string; project_id: string; conversation_id: string; task_id: string; question: string; answer: string; created: number };
export const getWorkLog = (limit = 15) => get<{ items: WorkItem[] }>(`/api/work-log?limit=${limit}`);
export const clearWorkLog = () => send<{ removed: number }>("DELETE", "/api/work-log");
export const updateMemoryNote =(id: string, patch: { text?: string; category?: string; project_id?: string | null }) =>
  send<{ item: MemoryNote; items: MemoryNote[] }>("PATCH", `/api/memory-notes/${id}`, patch);
export const putPrefs = (v: { profile: Profile; prefs: Prefs }) => send<PrefsView>("PUT", "/api/prefs", v);

export type ProjectSettings = { context: string; instructions: string[]; skills: string[]; files: string[]; tools_off: string[]; memory_on: boolean };
export type GeneratedFile = { name: string; path: string; kind: string | null; size: number | null; session_id: string; session_title: string; time: number };
export const getProjectGenerated = (id: string) => get<{ files: GeneratedFile[] }>(`/api/projects/${id}/generated`);
export const clearProjectMemory = (id: string) => send<{ removed: number; items: MemoryNote[] }>("DELETE", `/api/projects/${id}/memory`);

/** The optional tools an agent profile or a project can switch off. */
export const OPTIONAL_TOOLS: { id: string; label: string }[] = [
  { id: "web_search", label: "Web search" },
  { id: "delegate_task", label: "Sub-agents (delegate_task)" },
  { id: "propose_memory", label: "Memory suggestions (propose_memory)" },
  { id: "ask_user", label: "Questions to the user (ask_user)" },
];

export type Agent = {
  id: string;
  name: string;
  model_id: string | null;
  effort: string | null;
  mode: "plan" | "ask" | "auto";
  tools_off: string[];
  skills: string[];
  instructions: string;
};
export type AgentInput = Omit<Agent, "id">;
export const listAgents = () => get<Agent[]>("/api/agents");
export const createAgent = (a: AgentInput) => send<Agent>("POST", "/api/agents", a);
export const updateAgent = (id: string, a: AgentInput) => send<Agent>("PUT", `/api/agents/${id}`, a);
export const deleteAgent = (id: string) => send<{ ok: boolean }>("DELETE", `/api/agents/${id}`);

export const answerPermission = (taskId: string, id: string, choice: string) =>
  send<{ ok: boolean }>("POST", `/api/tasks/${taskId}/permission`, { id, choice });
export type Grant = { scope: "conversation" | "project" | "global"; key: string; tool: string };
export const listGrants = () => get<{ grants: Grant[] }>("/api/grants");
export const revokeGrant = (g: Grant) =>
  send<{ grants: Grant[] }>("DELETE", `/api/grants?scope=${g.scope}&tool=${encodeURIComponent(g.tool)}&key=${encodeURIComponent(g.key)}`);
export const getProjectSettings = (id: string) => get<ProjectSettings>(`/api/projects/${id}/settings`);
export const putProjectSettings = (id: string, v: ProjectSettings) => send<ProjectSettings>("PUT", `/api/projects/${id}/settings`, v);

export const setModelHidden = (id: string, hidden: boolean) => send<ModelsView>("PUT", `/api/models/${id}/hidden`, { hidden });

export type Connections = {
  chatgpt: { logged_in: boolean };
  providers: Provider[];
  data_path: string;
  workdir: string;
};
export const getConnections = () => get<Connections>("/api/connections");

export type DataInfo = { conversations: number; tasks: number; events: number; published: number; db_bytes: number; uploads_bytes: number; published_bytes: number };
export const getDataInfo = () => get<DataInfo>("/api/data/info");
export const clearAllData = () => send<{ deleted: number }>("POST", "/api/data/clear", { confirm: "clear" });
export async function downloadExport(): Promise<void> {
  const r = await fetch(`${API}/api/data/export`);
  if (!r.ok) throw new Error(tr("Export failed (HTTP {status})", { status: r.status }));
  const url = URL.createObjectURL(await r.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = "biomni-lite-export.json";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export type CatalogModel = {
  id: string;
  name: string;
  context: number | null;
  prompt_per_m: number | null;
  completion_per_m: number | null;
  free: boolean;
  efforts: string[];
  default_effort: string | null;
};
export type CatalogResult = { available: boolean; results: CatalogModel[]; have: string[] };
export const searchCatalog = (q: string, freeOnly: boolean) =>
  get<CatalogResult>(`/api/catalog?q=${encodeURIComponent(q)}&free=${freeOnly}&limit=30`);
export const restoreModels = () => send<ModelsView & { restored: number }>("POST", "/api/models/restore");
export const setModelEffort = (id: string, effort: string) => send<ModelsView>("PUT", `/api/models/${id}/effort`, { effort });

export type Provider = { id: string; name: string; base_url: string; local: boolean; builtin: boolean; has_key: boolean; ready: boolean };
export type ProviderPreset = { id: string; name: string; base_url: string; local: boolean; note: string };
export const listProviders = () => get<{ providers: Provider[]; presets: ProviderPreset[] }>("/api/providers");
export const addProvider = (b: { name: string; base_url: string; api_key: string; preset?: string }) => send<Provider>("POST", "/api/providers", b);
export const updateProvider = (id: string, b: { name?: string; base_url?: string; api_key?: string }) => send<Provider>("PATCH", `/api/providers/${id}`, b);
export const deleteProvider = (id: string) => send<{ ok: boolean; models_removed: number } & ModelsView>("DELETE", `/api/providers/${id}`);
export const testProvider = (id: string) => send<{ ok: boolean; count?: number; error?: string; seconds: number }>("POST", `/api/providers/${id}/test`);

export type ProviderModels = { available: boolean; error?: string; results: CatalogModel[]; have: string[]; rich?: boolean; total?: number };
export const providerModels = (id: string, q: string, freeOnly: boolean) =>
  get<ProviderModels>(`/api/providers/${id}/models?q=${encodeURIComponent(q)}&free=${freeOnly}&limit=40`);
