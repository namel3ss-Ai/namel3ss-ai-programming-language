import React from "react";
import { AgentTraceSummary } from "../api/types";

interface AgentTraceTabsProps {
  traces: AgentTraceSummary[];
  activeTraceId: string | null;
  onSelectTrace: (id: string) => void;
}

const AgentTraceTabs: React.FC<AgentTraceTabsProps> = ({ traces, activeTraceId, onSelectTrace }) => {
  if (!traces || traces.length === 0) {
    return <div className="empty-state">No agent runs yet.</div>;
  }
  return (
    <div className="trace-tabs">
      {traces.map((trace) => (
        <button
          key={trace.id}
          className={`trace-tab ${activeTraceId === trace.id ? "active" : ""}`}
          onClick={() => onSelectTrace(trace.id)}
        >
          <div className="trace-label">{trace.agent_name}</div>
          <div className="trace-meta">
            {trace.team_name && <span>{trace.team_name}</span>}
            {trace.role && <span className="chip">{trace.role}</span>}
            {trace.status && <span className="chip">{trace.status}</span>}
          </div>
        </button>
      ))}
    </div>
  );
};

export default AgentTraceTabs;
