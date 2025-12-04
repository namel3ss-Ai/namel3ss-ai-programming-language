import React from "react";
import { FlowGraph, TraceEvent } from "../api/types";

interface FlowStepListProps {
  graph: FlowGraph | null | undefined;
  events: TraceEvent[] | undefined;
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string) => void;
}

const FlowStepList: React.FC<FlowStepListProps> = ({ graph, events, selectedNodeId, onSelectNode }) => {
  const nodes = graph?.nodes || [];
  return (
    <div className="step-list">
      <div className="step-list-head">
        <h4>Steps</h4>
      </div>
      {nodes.length === 0 ? (
        <div className="empty-state">No steps recorded for this trace.</div>
      ) : (
        <ul>
          {nodes.map((node) => {
            const nodeEvents = (events || []).filter((e) => e.node_id === node.id);
            const duration = node.duration_seconds !== undefined ? `${node.duration_seconds.toFixed(2)}s` : null;
            return (
              <li
                key={node.id}
                className={selectedNodeId === node.id ? "active" : ""}
                onClick={() => onSelectNode(node.id)}
              >
                <div className="step-title">
                  <strong>{node.label}</strong> <span className="muted">({node.kind})</span>
                </div>
                <div className="step-meta">
                  {duration && <span>{duration}</span>}
                  {node.cost !== undefined && <span>cost: {node.cost}</span>}
                  {nodeEvents.length > 0 && <span>{nodeEvents.length} event(s)</span>}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
};

export default FlowStepList;
