export type DiagnosticSeverity = "error" | "warning" | "info";

export interface DiagnosticRange {
  start: {
    line: number;
    column: number;
  };
  end: {
    line: number;
    column: number;
  };
}

export interface Diagnostic {
  code: string;
  severity: DiagnosticSeverity;
  category?: string | null;
  message: string;
  location?: string | null;
  hint?: string | null;
  range?: DiagnosticRange | null;
  file?: string | null;
  auto_fix?: Record<string, unknown> | null;
  source?: string | null;
}

export interface DiagnosticsSummary {
  errors?: number;
  warnings?: number;
  infos?: number;
  error_count?: number;
  warning_count?: number;
  info_count?: number;
  strict?: boolean;
  [key: string]: number | boolean | undefined;
}

export interface DiagnosticsResponse {
  success?: boolean;
  diagnostics: Diagnostic[];
  summary: DiagnosticsSummary;
}

export interface OptimizationSuggestion {
  id: string;
  kind: string;
  status: string;
  severity: string;
  title: string;
  description: string;
  reason: string;
  target: Record<string, any>;
  actions: Record<string, any>[];
  created_at?: string;
}

export interface OptimizerSuggestionsResponse {
  suggestions: OptimizationSuggestion[];
}

export interface OptimizerScanResponse {
  created: string[];
}

export interface FlowSummary {
  name: string;
  description?: string | null;
  steps: number;
}

export interface TriggerSummary {
  id: string;
  kind: string;
  flow_name: string;
  enabled: boolean;
  config: Record<string, any>;
  last_fired: string | null;
}

export interface TraceSummary {
  id: string;
  flow_name?: string | null;
  started_at: string;
  status?: string | null;
  duration_seconds?: number | null;
}

export interface AgentTraceSummary {
  id: string;
  agent_name: string;
  team_name?: string;
  role?: string;
  started_at: string;
  finished_at?: string;
  status?: string;
  duration_seconds?: number;
  cost?: number;
}

export interface FlowNode {
  id: string;
  label: string;
  kind: string;
  duration_seconds?: number;
  cost?: number;
  token_usage?: {
    prompt_tokens?: number;
    completion_tokens?: number;
    total_tokens?: number;
  };
}

export interface FlowEdge {
  from: string;
  to: string;
}

export interface FlowGraph {
  nodes: FlowNode[];
  edges: FlowEdge[];
}

export type TraceScope = "flow" | "agent" | string;

export interface BaseTraceEvent {
  id: string;
  node_id?: string;
  timestamp?: string;
  kind?: string;
  message?: string;
  event?: string;
  scope?: TraceScope;
  [key: string]: any;
}

export interface ConditionEvalEvent extends BaseTraceEvent {
  event: "condition.eval" | "flow.condition.eval" | "agent.condition.eval";
  scope?: "flow" | "agent";
  condition?: string;
  expression?: string;
  result?: boolean;
  evaluated?: boolean;
  taken?: boolean;
  branch?: string | null;
  binding?: { name?: string; value?: unknown };
  macro?: string;
}

export interface PatternConditionEvalEvent extends BaseTraceEvent {
  event: "condition.pattern.eval" | "agent.condition.pattern.eval" | "flow.condition.pattern.eval";
  scope?: "flow" | "agent";
  condition?: string;
  result?: boolean;
  evaluated?: boolean;
  taken?: boolean;
  branch?: string | null;
  binding?: { name?: string; value?: unknown };
  pattern?: Record<string, unknown>;
}

export interface RuleGroupConditionEvalEvent extends BaseTraceEvent {
  event: "condition.rulegroup.eval" | "agent.condition.rulegroup.eval" | "flow.condition.rulegroup.eval";
  scope?: "flow" | "agent";
  rulegroup?: string;
  condition?: string;
  results?: Record<string, boolean>;
  result?: boolean;
  evaluated?: boolean;
  taken?: boolean;
}

export interface FlowGotoEvent extends BaseTraceEvent {
  event: "flow.goto";
  from_flow?: string;
  to_flow?: string;
  step?: string;
  reason?: string;
}

export type TraceEvent =
  | ConditionEvalEvent
  | PatternConditionEvalEvent
  | RuleGroupConditionEvalEvent
  | FlowGotoEvent
  | BaseTraceEvent;

export interface TraceDetail {
  id: string;
  flow_name?: string | null;
  started_at: string;
  status?: string | null;
  duration_seconds?: number | null;
  graph?: FlowGraph;
  events?: TraceEvent[];
  trace?: any;
}

export interface AgentToolCall {
  name: string;
  args: Record<string, unknown>;
  result_preview?: string | null;
}

export interface AgentMemoryEvent {
  space: string;
  type: string;
  key?: string | null;
  preview?: string | null;
}

export interface AgentRAGEvent {
  index?: string | null;
  query_preview: string;
  hit_count: number;
  token_usage?: {
    prompt_tokens?: number;
    completion_tokens?: number;
    total_tokens?: number;
  };
}

export interface AgentTraceStep {
  id: string;
  step_name: string;
  kind: string;
  target?: string | null;
  started_at: string;
  finished_at?: string | null;
  success: boolean;
  retries: number;
  evaluation_score?: number | null;
  evaluation_verdict?: string | null;
  message_preview?: string | null;
  tool_calls: AgentToolCall[];
  memory_events: AgentMemoryEvent[];
  rag_events: AgentRAGEvent[];
}

export interface AgentConversationMessage {
  id: string;
  role: string;
  content_preview: string;
  timestamp: string;
  related_step_id?: string | null;
}

export interface AgentTraceDetail {
  id: string;
  agent_name: string;
  team_name?: string;
  role?: string;
  started_at: string;
  finished_at?: string | null;
  status?: string;
  duration_seconds?: number;
  cost?: number;
  token_usage?: {
    prompt_tokens?: number;
    completion_tokens?: number;
    total_tokens?: number;
  };
  steps: AgentTraceStep[];
  messages?: AgentConversationMessage[];
}

export interface PagesResponse {
  pages: { name: string; route?: string; title?: string }[];
}

export interface PageUIResponse {
  ui: any;
  components: any[];
}

export interface RunAppResponse {
  status?: string;
  message?: string;
  error?: string | null;
  result?: any;
  trace?: any;
}

export interface JobsResponse {
  jobs: any[];
}

export interface MetricsResponse {
  metrics: Record<string, any>;
}

export interface StudioSummaryResponse {
  summary: Record<string, any>;
}

export interface TraceResponse {
  trace: any;
}

export interface RAGQueryResponse {
  results: any[];
}

export interface FlowsResponse {
  flows: FlowSummary[];
}

export interface TriggerListResponse {
  triggers: TriggerSummary[];
}

export interface TriggerFireResponse {
  job_id?: string | null;
}

export interface PluginMetadata {
  id: string;
  name: string;
  version: string | null | undefined;
  description?: string | null;
  entrypoints: Record<string, unknown>;
  tags: string[];
  compatible?: boolean;
  enabled?: boolean;
  loaded?: boolean;
  errors?: string[];
  path?: string | null;
  contributions?: Record<string, string[]>;
}

export type PluginInfo = PluginMetadata;

export interface PluginsResponse {
  plugins: PluginMetadata[];
}

export interface PluginLoadResponse {
  plugin: any;
}

export interface FmtPreviewResponse {
  formatted: string;
  changes_made: boolean;
}

export interface MemorySessionInfo {
  id: string;
  last_activity?: string | null;
  turns: number;
  user_id?: string | null;
}

export interface MemorySessionsResponse {
  ai: string;
  sessions: MemorySessionInfo[];
}

export interface MemoryTurn {
  role: string;
  content: string;
  created_at?: string | null;
}

export interface MemoryPolicyInfo {
  scope: string;
  requested_scope: string;
  scope_fallback?: boolean;
  scope_note?: string | null;
  retention_days?: number | null;
  pii_policy: string;
}

export interface MemorySessionDetail {
  ai: string;
  session: string;
  user_id?: string | null;
  short_term: {
    window?: number | null;
    turns: MemoryTurn[];
  };
  long_term?: {
    store?: string | null;
    items: { id: string; summary: string; created_at?: string | null }[];
  } | null;
  profile?: {
    store?: string | null;
    facts: string[];
  } | null;
  policies?: {
    short_term?: MemoryPolicyInfo | null;
    long_term?: MemoryPolicyInfo | null;
    profile?: MemoryPolicyInfo | null;
  };
  last_recall_snapshot?: {
    timestamp?: string;
    rules: { source?: string | null; count?: number | null; top_k?: number | null; include?: boolean | null }[];
    messages: { role: string; content: string }[];
  } | null;
}
