from __future__ import annotations

import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set

from ..errors import Namel3ssError


@dataclass
class GraphNode:
    id: str
    text: str | None = None
    source_id: Any | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    source: str
    target: str
    relation: str = "related_to"


@dataclass
class GraphData:
    nodes: Dict[str, GraphNode] = field(default_factory=dict)
    edges: List[GraphEdge] = field(default_factory=list)
    summaries: List[dict[str, Any]] = field(default_factory=list)


class GraphEngine:
    """
    Minimal graph builder and query engine for graph-aware RAG.
    """

    def __init__(self, graphs: dict[str, Any] | None = None, graph_summaries: dict[str, Any] | None = None) -> None:
        self.graph_defs = graphs or {}
        self.summary_defs = graph_summaries or {}
        self._graphs: dict[str, GraphData] = {}
        self._summaries: dict[str, list[dict[str, Any]]] = {}

    def has_graph(self, name: str) -> bool:
        return name in self._graphs

    def build_graph(self, name: str, frames: Any) -> GraphData:
        if name in self._graphs:
            return self._graphs[name]
        cfg = self.graph_defs.get(name)
        if cfg is None:
            raise Namel3ssError(f"Graph '{name}' is not declared.")
        if frames is None:
            raise Namel3ssError(f"Frame registry is not available to build graph '{name}'.")
        rows = frames.query(cfg.source_frame, None)
        data = GraphData()
        for row in rows:
            if not isinstance(row, dict):
                continue
            node_id = str(row.get(cfg.id_column, "")) if cfg.id_column else str(row.get("id", ""))
            text = str(row.get(cfg.text_column, "") if cfg.text_column else row.get("text", ""))
            entities = self._extract_entities(text, cfg.max_entities_per_doc)
            for ent in entities:
                node_key = ent.lower()
                if node_key not in data.nodes:
                    data.nodes[node_key] = GraphNode(id=node_key, text=ent, source_id=node_id, metadata={"entities": [ent]})
            # naive relations: connect consecutive entities in the same doc
            for idx in range(len(entities) - 1):
                src = entities[idx].lower()
                tgt = entities[idx + 1].lower()
                if src != tgt:
                    data.edges.append(GraphEdge(source=src, target=tgt, relation="related_to"))
        self._graphs[name] = data
        return data

    def build_summary(self, name: str, frames: Any) -> list[dict[str, Any]]:
        if name in self._summaries:
            return self._summaries[name]
        cfg = self.summary_defs.get(name)
        if cfg is None:
            raise Namel3ssError(f"Graph summary '{name}' is not declared.")
        graph_data = self.build_graph(cfg.graph, frames)
        components = self._connected_components(graph_data)
        summaries: list[dict[str, Any]] = []
        limit = None
        if cfg.max_nodes_per_summary is not None:
            try:
                limit = int(cfg.max_nodes_per_summary.value) if hasattr(cfg.max_nodes_per_summary, "value") else int(cfg.max_nodes_per_summary)
            except Exception:
                limit = None
        for comp in components:
            node_names = [graph_data.nodes[n].text or n for n in comp if n in graph_data.nodes]
            if limit:
                node_names = node_names[:limit]
            summary_text = f"Summary of {cfg.graph}: " + ", ".join(node_names)
            summaries.append({"nodes": list(comp), "text": summary_text})
        self._summaries[name] = summaries
        return summaries

    def query(self, graph_name: str, query_text: str, max_hops: int = 2, max_nodes: int = 25, strategy: str | None = None, frames: Any = None) -> list[dict[str, Any]]:
        graph_data = self.build_graph(graph_name, frames)
        seeds = self._extract_entities(query_text, None)
        if not seeds:
            return []
        seed_ids = [s.lower() for s in seeds if s]
        visited: Set[str] = set()
        queue: deque[tuple[str, int]] = deque()
        for s in seed_ids:
            if s in graph_data.nodes:
                queue.append((s, 0))
                visited.add(s)
        results: list[dict[str, Any]] = []
        adjacency = defaultdict(list)
        for edge in graph_data.edges:
            adjacency[edge.source].append((edge.target, edge.relation))
            adjacency[edge.target].append((edge.source, edge.relation))
        while queue and len(visited) < max_nodes:
            current, depth = queue.popleft()
            node = graph_data.nodes.get(current)
            if node:
                edges_desc = ", ".join(f"{current} -[{rel}]-> {nbr}" for nbr, rel in adjacency.get(current, []))
                results.append({"text": f"Node {node.text or node.id}: {edges_desc}", "node": node.id})
            if depth >= max_hops:
                continue
            for nbr, rel in adjacency.get(current, []):
                if nbr in visited or len(visited) >= max_nodes:
                    continue
                visited.add(nbr)
                queue.append((nbr, depth + 1))
        return results

    def lookup_summary(self, summary_name: str, query_text: str, top_k: int = 5, frames: Any = None) -> list[dict[str, Any]]:
        summaries = self.build_summary(summary_name, frames)
        seeds = self._extract_entities(query_text, None)
        seed_ids = {s.lower() for s in seeds}
        ranked: list[dict[str, Any]] = []
        for entry in summaries:
            nodes = set(entry.get("nodes") or [])
            score = 1
            if seed_ids and nodes:
                overlap = len(seed_ids.intersection(nodes))
                score = overlap if overlap > 0 else 0
            ranked.append({"text": entry.get("text"), "score": score, "nodes": entry.get("nodes", [])})
        ranked.sort(key=lambda x: x.get("score", 0), reverse=True)
        return ranked[:top_k]

    def _connected_components(self, graph: GraphData) -> list[set[str]]:
        adjacency = defaultdict(list)
        for edge in graph.edges:
            adjacency[edge.source].append(edge.target)
            adjacency[edge.target].append(edge.source)
        seen: set[str] = set()
        components: list[set[str]] = []
        for node_id in graph.nodes.keys():
            if node_id in seen:
                continue
            comp: set[str] = set()
            stack = [node_id]
            while stack:
                current = stack.pop()
                if current in seen:
                    continue
                seen.add(current)
                comp.add(current)
                for nbr in adjacency.get(current, []):
                    if nbr not in seen:
                        stack.append(nbr)
            components.append(comp)
        return components

    def _extract_entities(self, text: str, max_entities: Any | None) -> list[str]:
        if not text:
            return []
        tokens = re.findall(r"[A-Z][a-zA-Z0-9_]+", text)
        unique: list[str] = []
        for tok in tokens:
            if tok not in unique:
                unique.append(tok)
        if max_entities:
            try:
                limit = int(max_entities.value) if hasattr(max_entities, "value") else int(max_entities)
                unique = unique[:limit]
            except Exception:
                pass
        return unique
