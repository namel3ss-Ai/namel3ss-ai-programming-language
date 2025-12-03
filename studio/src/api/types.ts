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
