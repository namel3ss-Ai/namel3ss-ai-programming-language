"""
IR package re-export surface. Temporarily proxies to legacy monolithic ir.py during refactor.
"""

from __future__ import annotations

import importlib
from typing import Any

_legacy = importlib.import_module("namel3ss.ir_legacy")

__all__ = getattr(_legacy, "__all__", None)
if __all__ is None:
    __all__ = [name for name in dir(_legacy) if not name.startswith("_")]

for _name in __all__:
    globals()[_name] = getattr(_legacy, _name)


def __getattr__(name: str) -> Any:
    return getattr(_legacy, name)
