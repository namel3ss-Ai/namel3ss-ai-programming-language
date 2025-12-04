import type { RunAppResponse, TraceDetail } from "../api/types";

export interface IDERunState {
  lastRunResponse: RunAppResponse | null;
  lastTrace: TraceDetail | null;
}

export function createInitialRunState(): IDERunState {
  return {
    lastRunResponse: null,
    lastTrace: null,
  };
}

export function applyRunResponse(state: IDERunState, response: RunAppResponse): IDERunState {
  return {
    ...state,
    lastRunResponse: response,
  };
}

export function applyLastTrace(state: IDERunState, trace: TraceDetail | null): IDERunState {
  return {
    ...state,
    lastTrace: trace,
  };
}
