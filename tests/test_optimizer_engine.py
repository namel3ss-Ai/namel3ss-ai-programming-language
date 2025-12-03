from datetime import datetime

from namel3ss.optimizer.engine import OptimizerEngine
from namel3ss.optimizer.models import OptimizationStatus
from namel3ss.optimizer.storage import OptimizerStorage
from namel3ss.metrics.tracker import MetricsTracker
from namel3ss.memory.engine import MemoryEngine
from namel3ss.memory.models import MemorySpaceConfig, MemoryType
from namel3ss.tools.registry import ToolRegistry
from pathlib import Path
import tempfile


def test_optimizer_engine_generates_flow_and_memory_suggestions():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "opt.db"
        storage = OptimizerStorage(db)
        metrics = MetricsTracker()
        # inject flow metrics
        metrics._flow_counters["flow:demo:runs"] = 10
        metrics._flow_counters["flow:demo:errors"] = 5
        mem = MemoryEngine([MemorySpaceConfig(name="long", type=MemoryType.CONVERSATION)])
        # populate memory
        for i in range(60):
            mem.add_item("long", f"msg {i}", MemoryType.CONVERSATION)
        engine = OptimizerEngine(storage=storage, metrics=metrics, memory_engine=mem)
        suggestions = engine.scan()
        assert any(s.kind.value == "flow-optimization" for s in suggestions)
        assert any(s.kind.value == "memory-policy" for s in suggestions)
        stored = storage.list()
        assert len(stored) >= 2
