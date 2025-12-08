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
  MemorySessionDetail,
  MemorySessionsResponse,
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

type StreamEventBase = {
  flow?: string;
  step?: string;
  channel?: string | null;
  role?: string | null;
  label?: string | null;
  mode?: string | null;
};

export type StreamEvent =
  | (StreamEventBase & { event: "ai_chunk"; delta: string })
  | (StreamEventBase & { event: "ai_done"; full: string })
  | (StreamEventBase & { event: "flow_done"; success: boolean; result: any })
  | (StreamEventBase & { event: "flow_error"; error: string; code?: string })
  | (StreamEventBase & { event: "state_change"; path: string; old_value?: any; new_value?: any });

export async function runFlowStreaming(flow: string, args: any, onEvent: (event: StreamEvent) => void): Promise<void> {
  const url = `${defaultBase}/api/ui/flow/stream`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": apiKey,
    },
    body: JSON.stringify({ flow, args }),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`API ${res.status}: ${detail}`);
  }
  if (!res.body) return;
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx = buffer.indexOf("\n");
    while (idx !== -1) {
      const line = buffer.slice(0, idx).trim();
      buffer = buffer.slice(idx + 1);
      if (line) {
        try {
          const evt = JSON.parse(line) as StreamEvent;
          onEvent(evt);
        } catch {
          // ignore malformed lines
        }
      }
      idx = buffer.indexOf("\n");
    }
  }
}

export function subscribeStateStream(onEvent: (event: StreamEvent) => void): () => void {
  const url = `${defaultBase}/api/ui/state/stream`;
  const controller = new AbortController();
  (async () => {
    const res = await fetch(url, {
      method: "GET",
      headers: {
        "X-API-Key": apiKey,
      },
      signal: controller.signal,
    });
    if (!res.ok || !res.body) {
      return;
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx = buffer.indexOf("\n");
      while (idx !== -1) {
        const line = buffer.slice(0, idx).trim();
        buffer = buffer.slice(idx + 1);
        if (line) {
          try {
            const evt = JSON.parse(line) as StreamEvent;
            onEvent(evt);
          } catch {
            // ignore malformed lines
          }
        }
        idx = buffer.indexOf("\n");
      }
    }
  })().catch(() => {
    // ignore subscription errors in preview mode
  });
  return () => controller.abort();
}

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
  fetchMemorySessions: (aiId: string) =>
    request<MemorySessionsResponse>(`/api/memory/ai/${encodeURIComponent(aiId)}/sessions`, {
      method: "GET",
    }),
  fetchMemorySessionDetail: (aiId: string, sessionId: string) =>
    request<MemorySessionDetail>(
      `/api/memory/ai/${encodeURIComponent(aiId)}/sessions/${encodeURIComponent(sessionId)}`,
      {
        method: "GET",
      },
    ),
  clearMemorySession: (aiId: string, sessionId: string, kinds?: string[]) =>
    request<{ success: boolean }>(
      `/api/memory/ai/${encodeURIComponent(aiId)}/sessions/${encodeURIComponent(sessionId)}/clear`,
      {
        method: "POST",
        body: JSON.stringify({ kinds }),
      },
    ),
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
  runFlowStreaming,
  subscribeStateStream,
};
