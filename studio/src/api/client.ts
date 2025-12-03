import {
  DiagnosticsResponse,
  JobsResponse,
  MetricsResponse,
  PageUIResponse,
  PagesResponse,
  RunAppResponse,
  StudioSummaryResponse,
  TraceResponse,
  RAGQueryResponse,
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
  fetchTrace: () => request<TraceResponse>("/api/last-trace"),
  fetchMetrics: () => request<MetricsResponse>("/api/metrics"),
  fetchStudioSummary: () => request<StudioSummaryResponse>("/api/studio-summary"),
  fetchDiagnostics: (code: string, strict: boolean) =>
    request<DiagnosticsResponse>(`/api/diagnostics?strict=${strict ? "true" : "false"}&format=json`, {
      method: "POST",
      body: JSON.stringify({ code }),
    }),
  fetchJobs: () => request<JobsResponse>("/api/jobs"),
  queryRag: (code: string, query: string, indexes?: string[]) =>
    request<RAGQueryResponse>("/api/rag/query", {
      method: "POST",
      body: JSON.stringify({ code, query, indexes }),
    }),
};
