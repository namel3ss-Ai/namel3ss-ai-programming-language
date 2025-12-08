from types import SimpleNamespace

from namel3ss.studio.engine import StudioEngine
from namel3ss.studio.models import DashboardSummary


class FakeJob:
    def __init__(self, status: str):
        self.status = status


def test_studio_engine_builds_summary():
    class FakeJobQueue:
        def list(self):
            return [FakeJob("queued"), FakeJob("running"), FakeJob("error")]

    class FakeMemoryStore:
        def __init__(self):
            self.items = {"short": [1, 2, 3]}

        def list(self, space=None):
            if space is None:
                return [1, 2, 3]
            return self.items.get(space, [])

    class FakeMemoryEngine:
        def __init__(self):
            self.store = FakeMemoryStore()
            self.spaces = {"short": True}

    class FakeRagStore:
        def __init__(self):
            self._chunks = [1, 2]

    class FakeRagEngine:
        def __init__(self):
            self.store = FakeRagStore()

    class FakePluginRegistry:
        def list_plugins(self):
            return [SimpleNamespace(name="p1"), SimpleNamespace(name="p2")]

    ir_program = SimpleNamespace(flows={"f": 1}, agents={"a": 1}, plugins={"p": 1}, ai_calls={"support_bot": object()})

    engine = StudioEngine(
        job_queue=FakeJobQueue(),
        tracer=None,
        metrics_tracker=None,
        memory_engine=FakeMemoryEngine(),
        rag_engine=FakeRagEngine(),
        ir_program=ir_program,
        plugin_registry=FakePluginRegistry(),
    )
    summary = engine.build_summary()
    assert isinstance(summary, DashboardSummary)
    assert summary.total_jobs == 3
    assert summary.running_jobs == 1
    assert summary.failed_jobs == 1
    assert summary.total_flows == 1
    assert summary.total_plugins == 2
    assert summary.memory_items == 3
    assert summary.rag_documents == 2
    assert summary.ai_calls == ["support_bot"]
