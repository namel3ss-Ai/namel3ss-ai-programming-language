import React from "react";
import { AgentTraceDetail, AgentTraceStep } from "../api/types";

interface AgentRolePanelProps {
  trace: AgentTraceDetail | null;
  selectedStep: AgentTraceStep | null;
}

const AgentRolePanel: React.FC<AgentRolePanelProps> = ({ trace, selectedStep }) => {
  if (!trace) {
    return <div className="empty-state">Select an agent run to inspect.</div>;
  }
  return (
    <div className="role-panel">
      <div className="detail-header">
        <h4>{trace.agent_name}</h4>
        {trace.role && <span className="chip">{trace.role}</span>}
        {trace.status && <span className="chip">{trace.status}</span>}
      </div>
      <div className="detail-meta">
        {trace.team_name && <span>Team: {trace.team_name}</span>}
        {trace.duration_seconds !== undefined && trace.duration_seconds !== null && (
          <span>Duration: {trace.duration_seconds.toFixed(2)}s</span>
        )}
        {trace.cost !== undefined && trace.cost !== null && <span>Cost: {trace.cost}</span>}
        {trace.token_usage && (
          <span>
            Tokens: {trace.token_usage.total_tokens ?? 0} (p:{trace.token_usage.prompt_tokens ?? 0} c:
            {trace.token_usage.completion_tokens ?? 0})
          </span>
        )}
      </div>
      {selectedStep && (
        <div className="muted">Selected step: {selectedStep.step_name} ({selectedStep.kind})</div>
      )}
    </div>
  );
};

export default AgentRolePanel;
