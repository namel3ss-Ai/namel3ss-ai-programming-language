import tempfile
from pathlib import Path
from datetime import datetime, timezone

from namel3ss.optimizer.apply import SuggestionApplier
from namel3ss.optimizer.models import OptimizationSuggestion, OptimizationKind, OptimizationStatus
from namel3ss.optimizer.storage import OptimizerStorage
from namel3ss.optimizer.overlays import OverlayStore, RuntimeOverlay


def test_apply_updates_overlays():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "opt.db"
        overlays = Path(tmp) / "overlays.json"
        storage = OptimizerStorage(db)
        store = OverlayStore(overlays)
        sugg = OptimizationSuggestion(
            id="s1",
            kind=OptimizationKind.MODEL_SELECTION,
        created_at=datetime.now(timezone.utc),
            status=OptimizationStatus.PENDING,
            severity="info",
            title="set model",
            description="",
            reason="",
            target={"model": "default"},
            actions=[{"type": "set_model", "target": {"model_name": "default"}, "params": {"provider": "dummy"}}],
            metrics_snapshot={},
        )
        storage.save(sugg)
        applier = SuggestionApplier(store, storage)
        applier.apply(sugg)
        overlay = store.load()
        assert "default" in overlay.models
        assert storage.get("s1").status == OptimizationStatus.APPLIED
