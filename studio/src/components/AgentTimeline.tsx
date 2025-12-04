import React from "react";
import { AgentTraceStep } from "../api/types";

interface AgentTimelineProps {
  steps: AgentTraceStep[];
  selectedStepId: string | null;
  onSelectStep: (id: string) => void;
}

const AgentTimeline: React.FC<AgentTimelineProps> = ({ steps, selectedStepId, onSelectStep }) => {
  if (!steps || steps.length === 0) {
    return <div className="empty-state">No steps recorded.</div>;
  }
  return (
    <div className="timeline">
      {steps.map((step) => (
        <div
          key={step.id}
          className={`timeline-step ${selectedStepId === step.id ? "active" : ""}`}
          onClick={() => onSelectStep(step.id)}
          title={step.step_name}
        >
          <span className="timeline-label">{step.step_name}</span>
          <span className="timeline-kind">{step.kind}</span>
        </div>
      ))}
    </div>
  );
};

export default AgentTimeline;
