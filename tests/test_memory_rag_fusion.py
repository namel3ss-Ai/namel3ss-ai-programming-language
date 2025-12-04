from dataclasses import dataclass
from datetime import UTC, datetime

from namel3ss.memory.fusion import fused_recall
from namel3ss.memory.models import MemoryNamespace, SemanticMemoryRecord
from namel3ss.memory.store import MemoryBackend


@dataclass
class FakeHit:
    text: str


class FakeRetrievalPipeline:
    def __init__(self, hits):
        self.hits = hits
        self.calls = 0

    def retrieve(self, query: str, top_k: int = 5):
        self.calls += 1
        return self.hits[:top_k]


def test_fused_recall_combines_memory_and_rag():
    backend = MemoryBackend()
    ns = MemoryNamespace(tenant_id="t", user_id="u", agent_id="a")
    backend.add_semantic(
        SemanticMemoryRecord(
            id="s1",
            namespace=ns,
            created_at=datetime.now(UTC),
            source_range={"ids": []},
            summary="Remember apples and oranges",
            metadata={},
        )
    )
    pipeline = FakeRetrievalPipeline([FakeHit("Document about apples"), FakeHit("Document about bananas")])
    result = fused_recall(ns, "apples", backend, pipeline, top_k=1)
    assert len(result.semantic_hits) == 1
    assert len(result.rag_hits) == 1
    assert "MEMORY" in result.combined_context and "DOC" in result.combined_context
