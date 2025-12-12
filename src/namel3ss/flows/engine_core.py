"""
Compatibility shim for engine core. Prefer importing from `namel3ss.flows.engine.core`.
"""

from __future__ import annotations

from .engine.core import FlowEngine

__all__ = ["FlowEngine"]
