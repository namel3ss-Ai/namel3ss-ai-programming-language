import {
  DiagnosticsResponse,
  JobsResponse,
  MetricsResponse,
  PageUIResponse,
  PagesResponse,
  RunAppResponse,
  StudioSummaryResponse,
  RAGQueryResponse,
  FlowsResponse,
  TriggerListResponse,
  TriggerFireResponse,
  PluginLoadResponse,
  OptimizerSuggestionsResponse,
  OptimizerScanResponse,
  TraceSummary,
  TraceDetail,
  AgentTraceSummary,
  AgentTraceDetail,
  FmtPreviewResponse,
  PluginMetadata,
  PluginsResponse,
} from "./types";

const defaultBase = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const apiKey = import.meta.env.VITE_N3_API_KEY || "dev-key";

async function request<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const url = `${defaultBase}${path}`;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-API-Key": apiKey,
    ...(opts.headers as Record<string, string> | undefined),
  };
  const res = await fetch(url, { ...opts, headers });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`API ${res.status}: ${detail}`);
  }
  return (await res.json()) as T;
}

export const postDiagnostics = (source: string) =>
  request<DiagnosticsResponse>("/api/diagnostics?format=json", {
    method: "POST",
    body: JSON.stringify({ code: source }),
  });

export const postFmtPreview = (source: string) =>
  request<FmtPreviewResponse>("/api/fmt/preview", {
    method: "POST",
    body: JSON.stringify({ source }),
  });

export const postRunApp = (code: string, appName: string) =>
  request<RunAppResponse>("/api/run-app", {
    method: "POST",
    body: JSON.stringify({ source: code, app_name: appName }),
  });

export const ApiClient = {
  fetchPages: (code: string) =>
    request<PagesResponse>("/api/pages", {
      method: "POST",
      body: JSON.stringify({ code }),
    }),
  fetchPageUI: (code: string, page: string) =>
    request<PageUIResponse>("/api/page-ui", {
      method: "POST",
      body: JSON.stringify({ code, page }),
    }),
  runApp: (code: string, app_name: string) =>
    request<RunAppResponse>("/api/run-app", {
      method: "POST",
      body: JSON.stringify({ source: code, app_name }),
    }),
  fetchTraces: () => request<TraceSummary[]>("/api/traces"),
  fetchTraceById: (id: string) => request<TraceDetail>(`/api/trace/${encodeURIComponent(id)}`),
  fetchLastTrace: () => request<TraceDetail>("/api/last-trace"),
  fetchAgentTraces: () => request<AgentTraceSummary[]>("/api/agent-traces"),
  fetchAgentTraceById: (id: string) => request<AgentTraceDetail>(`/api/agent-trace/${encodeURIComponent(id)}`),
  fetchMetrics: () => request<MetricsResponse>("/api/metrics"),
  fetchStudioSummary: () => request<StudioSummaryResponse>("/api/studio-summary"),
  fetchDiagnostics: (code: string, strict: boolean) =>
    request<DiagnosticsResponse>(`/api/diagnostics?strict=${strict ? "true" : "false"}&format=json`, {
      method: "POST",
      body: JSON.stringify({ code }),
    }),
  postDiagnostics,
  fetchJobs: () => request<JobsResponse>("/api/jobs"),
  queryRag: (code: string, query: string, indexes?: string[]) =>
    request<RAGQueryResponse>("/api/rag/query", {
      method: "POST",
      body: JSON.stringify({ code, query, indexes }),
    }),
  fetchFlows: (code: string) =>
    request<FlowsResponse>("/api/flows", {
      method: "POST",
      body: JSON.stringify({ code }),
    }),
  fetchTriggers: () => request<TriggerListResponse>("/api/flows/triggers"),
  fireTrigger: (triggerId: string, payload?: any) =>
    request<TriggerFireResponse>(`/api/flows/trigger/${triggerId}`, {
      method: "POST",
      body: JSON.stringify({ payload }),
    }),
  fetchPlugins: async (): Promise<PluginMetadata[]> => {
    const res = await request<PluginsResponse>("/api/plugins");
    return res.plugins || [];
  },
  loadPlugin: (id: string) =>
    request<PluginLoadResponse>(`/api/plugins/${id}/load`, {
      method: "POST",
    }),
  unloadPlugin: (id: string) =>
    request(`/api/plugins/${id}/unload`, {
      method: "POST",
    }),
  fetchOptimizerSuggestions: (status?: string) =>
    request<OptimizerSuggestionsResponse>(`/api/optimizer/suggestions${status ? `?status=${status}` : ""}`),
  scanOptimizer: () =>
    request<OptimizerScanResponse>(`/api/optimizer/scan`, {
      method: "POST",
    }),
  applySuggestion: (id: string) =>
    request(`/api/optimizer/apply/${id}`, {
      method: "POST",
    }),
  rejectSuggestion: (id: string) =>
    request(`/api/optimizer/reject/${id}`, {
      method: "POST",
    }),
  postFmtPreview,
  postRunApp,
};
