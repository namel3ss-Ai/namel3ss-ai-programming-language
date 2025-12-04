import React from "react";
import type { RunAppResponse, TraceDetail } from "../api/types";

export interface RunOutputPanelProps {
  lastRun: RunAppResponse | null;
  lastTrace: TraceDetail | null;
  onRefresh: () => void;
  isRefreshing: boolean;
  onViewTrace?: (traceId: string) => void;
  className?: string;
}

export const RunOutputPanel: React.FC<RunOutputPanelProps> = ({
  lastRun,
  lastTrace,
  onRefresh,
  isRefreshing,
  onViewTrace,
  className,
}) => {
  return (
    <div className={className ?? "n3-run-output-panel"}>
      <div className="n3-run-output-header">
        <h3>Run Output</h3>
        <button type="button" onClick={onRefresh} disabled={isRefreshing}>
          {isRefreshing ? "Refreshing..." : "Refresh"}
        </button>
      </div>
      <div className="n3-run-output-body">
        <section className="n3-run-output-section">
          <h4>Last Run Response</h4>
          {!lastRun && <div>No runs yet.</div>}
          {lastRun && (
            <div className="n3-run-output-run">
              <div>Status: {lastRun.status ?? "unknown"}</div>
              {lastRun.message && <div>Message: {lastRun.message}</div>}
              {lastRun.error && <div>Error: {lastRun.error}</div>}
            </div>
          )}
        </section>
        <section className="n3-run-output-section">
          <h4>Last Trace</h4>
          {!lastTrace && <div>No last trace available.</div>}
          {lastTrace && (
            <div className="n3-run-output-trace">
              <div>ID: {lastTrace.id}</div>
              {lastTrace.kind && <div>Type: {lastTrace.kind}</div>}
              {lastTrace.status && <div>Status: {lastTrace.status}</div>}
              {lastTrace.started_at && <div>Started at: {String(lastTrace.started_at)}</div>}
              {onViewTrace && (
                <button
                  type="button"
                  className="n3-run-output-view-trace-button"
                  onClick={() => onViewTrace(lastTrace.id)}
                >
                  View full trace
                </button>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  );
};
