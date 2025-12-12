"""Application package for Namel3ss FastAPI server."""

from __future__ import annotations

from .factory import create_app

# Build a module-level app instance for legacy imports.
app = create_app()

__all__ = ["create_app", "app"]
