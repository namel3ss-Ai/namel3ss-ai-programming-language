import tempfile
from datetime import datetime, timezone
from pathlib import Path

from namel3ss.optimizer.models import OptimizationSuggestion, OptimizationKind, OptimizationStatus
from namel3ss.optimizer.storage import OptimizerStorage


def test_optimizer_storage_round_trip():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "opt.db"
        storage = OptimizerStorage(db)
        sug = OptimizationSuggestion(
            id="s1",
            kind=OptimizationKind.FLOW_OPTIMIZATION,
            created_at=datetime.now(timezone.utc),
            status=OptimizationStatus.PENDING,
            severity="warning",
            title="Test",
            description="desc",
            reason="high_error",
            target={"flow": "f1"},
            actions=[{"type": "set_model", "target": {"model_name": "m"}, "params": {}}],
            metrics_snapshot={"runs": 10},
        )
        storage.save(sug)
        got = storage.get("s1")
        assert got is not None
        assert got.target["flow"] == "f1"
        got.status = OptimizationStatus.APPLIED
        storage.update(got)
        listed = storage.list(OptimizationStatus.APPLIED)
        assert len(listed) == 1
