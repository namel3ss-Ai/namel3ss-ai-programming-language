"""Compatibility shim for the Namel3ss FastAPI server."""

from __future__ import annotations

from .server.app import app, create_app

__all__ = ["create_app", "app"]
