import React from "react";
import { FlowNode, TraceDetail, TraceEvent } from "../api/types";

interface FlowStepDetailsProps {
  trace: TraceDetail | null;
  selectedNode: FlowNode | null;
  eventsForNode: TraceEvent[];
}

const Section: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
  <div className="detail-section">
    <h5>{title}</h5>
    {children}
  </div>
);

const FlowStepDetails: React.FC<FlowStepDetailsProps> = ({ trace, selectedNode, eventsForNode }) => {
  if (!trace) {
    return <div className="empty-state">Select a trace to inspect details.</div>;
  }
  if (!selectedNode) {
    return <div className="empty-state">Select a step to see details.</div>;
  }

  const tokens = selectedNode.token_usage;

  return (
    <div className="step-details">
      <div className="detail-header">
        <h4>{selectedNode.label}</h4>
        <span className="chip">{selectedNode.kind}</span>
      </div>
      <div className="detail-meta">
        {selectedNode.duration_seconds !== undefined && <span>Duration: {selectedNode.duration_seconds.toFixed(2)}s</span>}
        {selectedNode.cost !== undefined && <span>Cost: {selectedNode.cost}</span>}
        {tokens && (
          <span>
            Tokens: {tokens.total_tokens ?? tokens.prompt_tokens ?? 0} (p:{tokens.prompt_tokens ?? 0} c:{tokens.completion_tokens ?? 0})
          </span>
        )}
      </div>

      <Section title="Raw Events">
        {eventsForNode.length === 0 ? (
          <div className="muted">No events for this step.</div>
        ) : (
          <pre>{JSON.stringify(eventsForNode, null, 2)}</pre>
        )}
      </Section>

      <Section title="Trace">
        <pre>{JSON.stringify(trace.trace, null, 2)}</pre>
      </Section>
    </div>
  );
};

export default FlowStepDetails;
