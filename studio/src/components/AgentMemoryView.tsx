import React, { useMemo } from "react";
import { AgentTraceStep } from "../api/types";

interface AgentMemoryViewProps {
  steps: AgentTraceStep[];
  selectedStepId: string | null;
}

const AgentMemoryView: React.FC<AgentMemoryViewProps> = ({ steps, selectedStepId }) => {
  const summary = useMemo(() => {
    let reads = 0;
    let writes = 0;
    let rag = 0;
    steps.forEach((step) => {
      step.memory_events.forEach((m) => {
        if (m.type === "read") reads += 1;
        if (m.type === "write") writes += 1;
      });
      rag += step.rag_events.length;
    });
    return { reads, writes, rag };
  }, [steps]);

  const selected = steps.find((s) => s.id === selectedStepId) || null;

  return (
    <div className="memory-view">
      <div className="detail-meta">
        <span>Memory reads: {summary.reads}</span>
        <span>Memory writes: {summary.writes}</span>
        <span>RAG queries: {summary.rag}</span>
      </div>
      {selected ? (
        <div>
          <h5>Selected step memory</h5>
          {selected.memory_events.length === 0 && selected.rag_events.length === 0 ? (
            <div className="muted">No memory or RAG events.</div>
          ) : (
            <>
              {selected.memory_events.length > 0 && (
                <div>
                  <strong>Memory</strong>
                  <pre>{JSON.stringify(selected.memory_events, null, 2)}</pre>
                </div>
              )}
              {selected.rag_events.length > 0 && (
                <div>
                  <strong>RAG</strong>
                  <pre>{JSON.stringify(selected.rag_events, null, 2)}</pre>
                </div>
              )}
            </>
          )}
        </div>
      ) : (
        <div className="muted">Select a step to view memory/RAG details.</div>
      )}
    </div>
  );
};

export default AgentMemoryView;
