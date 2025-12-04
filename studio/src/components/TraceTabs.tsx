import React from "react";
import { TraceSummary } from "../api/types";

interface TraceTabsProps {
  traces: TraceSummary[];
  activeTraceId: string | null;
  onSelectTrace: (id: string) => void;
}

const TraceTabs: React.FC<TraceTabsProps> = ({ traces, activeTraceId, onSelectTrace }) => {
  if (!traces || traces.length === 0) {
    return <div className="empty-state">No traces yet.</div>;
  }
  return (
    <div className="trace-tabs">
      {traces.map((trace) => (
        <button
          key={trace.id}
          className={`trace-tab ${activeTraceId === trace.id ? "active" : ""}`}
          onClick={() => onSelectTrace(trace.id)}
        >
          <div className="trace-label">{trace.flow_name || "trace"}</div>
          <div className="trace-meta">
            <span>{new Date(trace.started_at).toLocaleTimeString()}</span>
            {trace.status && <span className="chip">{trace.status}</span>}
            {trace.duration_seconds !== undefined && trace.duration_seconds !== null && (
              <span>{trace.duration_seconds.toFixed(2)}s</span>
            )}
          </div>
        </button>
      ))}
    </div>
  );
};

export default TraceTabs;
