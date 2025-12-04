import asyncio
from datetime import UTC, datetime, timedelta

from namel3ss.memory.models import EpisodicMemoryRecord, MemoryNamespace, RetentionPolicy
from namel3ss.memory.store import MemoryBackend
from namel3ss.memory.summarization_worker import MemorySummarizationWorker


class FakeRouter:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls = 0

    def generate(self, messages):
        self.calls += 1
        return type("Resp", (), {"text": self.text})


def test_summarization_worker_creates_semantic_records_and_prunes():
    backend = MemoryBackend()
    ns = MemoryNamespace(tenant_id="t", user_id="u", agent_id="a")
    now = datetime.now(UTC)
    for i in range(4):
        backend.add_episodic(
            EpisodicMemoryRecord(
                id=f"e{i}",
                namespace=ns,
                timestamp=now - timedelta(minutes=i + 1),
                kind="event",
                content=f"content {i}",
                metadata={},
            )
        )
    router = FakeRouter("summary text")
    worker = MemorySummarizationWorker(
        backend=backend,
        model_router=router,
        retention_policy=RetentionPolicy(max_episodes_per_namespace=1),
        min_age_seconds=0,
        max_window=2,
    )
    report = asyncio.run(worker.run_once())
    assert report.summaries_created >= 2
    assert router.calls == report.summaries_created
    assert len(backend.semantic) == report.summaries_created
    assert report.pruned > 0
