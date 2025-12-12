from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # repo root
ENGINE_SHIM = ROOT / "src" / "namel3ss" / "flows" / "engine.py"
ENGINE_CORE_SHIM = ROOT / "src" / "namel3ss" / "flows" / "engine_core.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_engine_shim_is_thin() -> None:
    content = _read(ENGINE_SHIM)
    assert content.count("\n") + 1 <= 80, "engine.py shim grew too large"
    forbidden = ("phases", "steps", "control", "adapters", "state")
    for needle in forbidden:
        assert needle not in content, f"engine.py shim must not import {needle}"
    assert "from .engine.public import" in content


def test_engine_core_shim_is_thin() -> None:
    content = _read(ENGINE_CORE_SHIM)
    assert content.count("\n") + 1 <= 80, "engine_core.py shim grew too large"
    forbidden = ("phases", "steps", "control", "adapters", "state")
    for needle in forbidden:
        assert needle not in content, f"engine_core.py shim must not import {needle}"
    assert "from .engine.core import" in content
