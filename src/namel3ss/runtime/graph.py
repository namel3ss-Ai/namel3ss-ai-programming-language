"""
Reasoning graph abstractions for the runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List


class NodeType(str, Enum):
    APP = "APP"
    PAGE = "PAGE"
    AI_CALL = "AI_CALL"
    AI_CALL_REF = "AI_CALL_REF"
    MODEL = "MODEL"
    AGENT = "AGENT"
    MEMORY = "MEMORY"
    FLOW = "FLOW"
    TOOL = "TOOL"


@dataclass
class GraphNode:
    id: str
    type: NodeType
    label: str | None = None
    data: object | None = None


@dataclass
class GraphEdge:
    source: str
    target: str
    label: str | None = None


@dataclass
class Graph:
    nodes: Dict[str, GraphNode] = field(default_factory=dict)
    edges: List[GraphEdge] = field(default_factory=list)
    adjacency: Dict[str, List[GraphEdge]] = field(default_factory=dict)

    def add_node(self, node: GraphNode) -> None:
        if node.id not in self.nodes:
            self.nodes[node.id] = node
            self.adjacency[node.id] = []

    def add_edge(self, edge: GraphEdge) -> None:
        self.edges.append(edge)
        self.adjacency.setdefault(edge.source, []).append(edge)

    def neighbors(self, node_id: str) -> List[GraphEdge]:
        return self.adjacency.get(node_id, [])
