import { tr } from "@/lib/i18n";

export const API = process.env.NEXT_PUBLIC_API ?? "http://127.0.0.1:8765";

export type ToolResult = { title: string; url: string; domain: string; snippet: string };
export type PlanStep = { text: string; status: "todo" | "done" | "failed" };
export type Artifact = { name: string; path: string; kind: "image" | "video" | "pdf" | "table" | "html" | "text"; mtime?: number; size?: number };

type Base = { seq: number; ts: number };
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
) =>
  send<{ id: string; conversation_id: string }>("POST", "/api/tasks", {
    prompt,
    conversation_id: conversationId,
    approval,
    mentions: mentions ?? [],
    project_id: projectId,
    mode: mode ?? "ask",
  });
export const cancelTask = (id: string) => send<{ ok: boolean }>("POST", `/api/tasks/${id}/cancel`);
export const reviewTask = (id: string) => send<AgentEvent>("POST", `/api/tasks/${id}/review`);
export const suggestTask = (id: string) => send<AgentEvent>("POST", `/api/tasks/${id}/suggest`);
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

export type SettingsValues = {
  source: string | null;
  model: string;
  use_tool_retriever: boolean;
  commercial_mode: boolean;
};
export type SettingsView = { values: SettingsValues; sources: Record<string, string>; custom_ready: boolean };
export const getSettings = () => get<SettingsView>("/api/settings");
export const putSettings = (s: Partial<SettingsValues>) => send<SettingsView>("PUT", "/api/settings", s);

export type Mention = { kind: "skill" | "tool" | "data" | "file"; id: string; label: string; hint: string };
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
};
export const getModels = () => get<ModelsView>("/api/models");
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
export const deleteProject = (id: string) => send<Project[]>("DELETE", `/api/projects/${id}`);
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
export type MemoryNote = { id: string; text: string; created: number };
export const getConnectors = () => get<{ connectors: Connector[] }>("/api/connectors");
export const setConnector = (id: string, enabled: boolean) => send<{ connectors: Connector[] }>("PUT", `/api/connectors/${id}`, { enabled });
export const getMemoryNotes = () => get<{ items: MemoryNote[] }>("/api/memory-notes");
export const deleteMemoryNote = (id: string) => send<{ items: MemoryNote[] }>("DELETE", `/api/memory-notes/${id}`);
export const putPrefs = (v: { profile: Profile; prefs: Prefs }) => send<PrefsView>("PUT", "/api/prefs", v);

export type ProjectSettings = { context: string; instructions: string[]; skills: string[] };
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
