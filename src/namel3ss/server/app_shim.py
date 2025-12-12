"""Compatibility shim that re-exports the packaged app factory."""

from __future__ import annotations

from .app import app, create_app

__all__ = ["create_app", "app"]
