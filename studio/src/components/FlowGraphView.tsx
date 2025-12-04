import React, { useMemo } from "react";
import { FlowGraph } from "../api/types";

interface FlowGraphViewProps {
  graph: FlowGraph | null | undefined;
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string) => void;
}

const FlowGraphView: React.FC<FlowGraphViewProps> = ({ graph, selectedNodeId, onSelectNode }) => {
  const layout = useMemo(() => {
    const nodes = graph?.nodes || [];
    const spacingX = 180;
    const spacingY = 120;
    return nodes.map((node, idx) => ({
      ...node,
      x: 40 + idx * spacingX,
      y: 60 + (idx % 2) * spacingY,
    }));
  }, [graph]);

  const edges = graph?.edges || [];

  const width = Math.max(600, layout.length * 180);
  const height = 260;

  return (
    <div className="flow-graph-view">
      <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} role="img">
        {edges.map((edge, idx) => {
          const from = layout.find((n) => n.id === edge.from);
          const to = layout.find((n) => n.id === edge.to);
          if (!from || !to) return null;
          return (
            <line
              key={idx}
              x1={from.x + 60}
              y1={from.y + 20}
              x2={to.x}
              y2={to.y + 20}
              stroke="#999"
              strokeWidth="2"
              markerEnd="url(#arrow)"
            />
          );
        })}
        <defs>
          <marker id="arrow" markerWidth="10" markerHeight="10" refX="6" refY="3" orient="auto" markerUnits="strokeWidth">
            <path d="M0,0 L0,6 L9,3 z" fill="#999" />
          </marker>
        </defs>
        {layout.map((node) => (
          <g key={node.id} onClick={() => onSelectNode(node.id)} style={{ cursor: "pointer" }}>
            <rect
              x={node.x}
              y={node.y}
              rx="10"
              ry="10"
              width="120"
              height="40"
              fill={selectedNodeId === node.id ? "#000" : "#f6f6f6"}
              stroke={selectedNodeId === node.id ? "#000" : "#ccc"}
              strokeWidth="2"
            />
            <text x={node.x + 60} y={node.y + 18} textAnchor="middle" fontSize="12" fontWeight="bold" fill={selectedNodeId === node.id ? "#fff" : "#000"}>
              {node.label}
            </text>
            <text x={node.x + 60} y={node.y + 32} textAnchor="middle" fontSize="10" fill={selectedNodeId === node.id ? "#eee" : "#555"}>
              {node.kind}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
};

export default FlowGraphView;
