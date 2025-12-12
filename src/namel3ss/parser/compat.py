"""Deprecation helper for moved parser symbols."""

from __future__ import annotations

import warnings


def deprecated_import(old: str, new: str) -> None:
    warnings.warn(f"{old} is deprecated; use {new}", DeprecationWarning, stacklevel=2)


__all__ = ["deprecated_import"]
