import React from "react";
import { AgentTraceStep } from "../api/types";

interface AgentStepDetailProps {
  step: AgentTraceStep | null;
}

const AgentStepDetail: React.FC<AgentStepDetailProps> = ({ step }) => {
  if (!step) {
    return <div className="empty-state">Select a step to inspect details.</div>;
  }
  return (
    <div className="step-details">
      <div className="detail-header">
        <h4>{step.step_name}</h4>
        <span className="chip">{step.kind}</span>
        <span className="chip">{step.success ? "success" : "failed"}</span>
      </div>
      <div className="detail-meta">
        {step.target && <span>Target: {step.target}</span>}
        <span>Retries: {step.retries}</span>
        {step.evaluation_score !== undefined && step.evaluation_score !== null && (
          <span>Score: {step.evaluation_score.toFixed(2)}</span>
        )}
        {step.evaluation_verdict && <span>Verdict: {step.evaluation_verdict}</span>}
      </div>
      {step.message_preview && (
        <div className="detail-section">
          <h5>Message</h5>
          <div className="muted">{step.message_preview}</div>
        </div>
      )}
      {step.tool_calls.length > 0 && (
        <div className="detail-section">
          <h5>Tool Calls</h5>
          <pre>{JSON.stringify(step.tool_calls, null, 2)}</pre>
        </div>
      )}
      {step.memory_events.length > 0 && (
        <div className="detail-section">
          <h5>Memory Events</h5>
          <pre>{JSON.stringify(step.memory_events, null, 2)}</pre>
        </div>
      )}
      {step.rag_events.length > 0 && (
        <div className="detail-section">
          <h5>RAG Events</h5>
          <pre>{JSON.stringify(step.rag_events, null, 2)}</pre>
        </div>
      )}
    </div>
  );
};

export default AgentStepDetail;
