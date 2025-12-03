export interface PageSummary {
  name: string;
  route: string | null;
  title: string | null;
  sections?: any[];
}

export interface PagesResponse {
  pages: PageSummary[];
}

export interface PageUIResponse {
  ui: {
    name: string;
    route: string | null;
    sections: { name: string; components: any[] }[];
  };
}

export interface RunAppResponse {
  app: any;
  entry_page: any;
  memories: any;
  graph: any;
  trace?: any;
}

export interface MetricsResponse {
  metrics: Record<string, any>;
}

export interface StudioSummary {
  total_jobs: number;
  running_jobs: number;
  failed_jobs: number;
  total_flows: number;
  total_agents: number;
  total_plugins: number;
  memory_items: number;
  rag_documents: number;
}

export interface StudioSummaryResponse {
  summary: StudioSummary;
}

export interface DiagnosticsSummary {
  error_count: number;
  warning_count: number;
  strict: boolean;
}

export interface DiagnosticEntry {
  code: string;
  severity: string;
  category: string;
  message: string;
  location?: string;
  hint?: string;
}

export interface DiagnosticsResponse {
  summary: DiagnosticsSummary;
  diagnostics: DiagnosticEntry[];
  text?: string;
}

export interface RAGQueryResult {
  text: string;
  score: number;
  source: string;
  metadata: Record<string, any>;
}

export interface RAGQueryResponse {
  results: RAGQueryResult[];
}

export interface TraceResponse {
  trace?: any;
}

export interface JobsResponse {
  jobs: {
    id: string;
    type: string;
    target: string;
    status: string;
    result?: any;
    error?: string;
  }[];
}
