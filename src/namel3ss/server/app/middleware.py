"""Middleware setup for the FastAPI app."""

from __future__ import annotations

from fastapi import FastAPI


def setup_middleware(app: FastAPI) -> None:
    """Configure middleware. Currently no-op to mirror legacy behavior."""
    return None


__all__ = ["setup_middleware"]
