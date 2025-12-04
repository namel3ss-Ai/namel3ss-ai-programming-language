"""
Memory + RAG fusion retrieval helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Protocol

from ..observability.tracing import default_tracer
from .models import MemoryNamespace, SemanticMemoryRecord
from .store import MemoryBackend


class RetrievalPipeline(Protocol):
    def retrieve(self, query: str, top_k: int = 5) -> List[Any]:
        ...


@dataclass
class FusionResult:
    semantic_hits: List[SemanticMemoryRecord]
    rag_hits: List[Any]
    combined_context: str
    metadata: Dict[str, Any]


def fused_recall(
    namespace: MemoryNamespace,
    query: str,
    memory_backend: MemoryBackend,
    retrieval_pipeline: RetrievalPipeline,
    top_k: int = 5,
) -> FusionResult:
    with default_tracer.span("memory.fused_recall", attributes={"namespace": namespace.key(), "query": query}):
        semantic_hits = [
            rec for rec in memory_backend.list_semantic(namespace) if query.lower() in rec.summary.lower()
        ][:top_k]
        rag_hits = retrieval_pipeline.retrieve(query, top_k=top_k) or []
        context_parts = []
        for rec in semantic_hits:
            context_parts.append(f"[MEMORY] {rec.summary}")
        for hit in rag_hits:
            content = getattr(hit, "text", None) or getattr(hit, "content", None) or str(hit)
            context_parts.append(f"[DOC] {content}")
        combined_context = "\n".join(context_parts)
        return FusionResult(
            semantic_hits=semantic_hits,
            rag_hits=rag_hits,
            combined_context=combined_context,
            metadata={"semantic_count": len(semantic_hits), "rag_count": len(rag_hits)},
        )
