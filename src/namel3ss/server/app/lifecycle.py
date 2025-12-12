"""Lifecycle hooks for the FastAPI app."""

from __future__ import annotations

from fastapi import FastAPI


def register_lifecycle(app: FastAPI, file_watcher) -> None:
    """Attach startup/shutdown handlers for the file watcher."""

    @app.on_event("startup")
    async def _startup_file_watcher() -> None:  # pragma: no cover - integration
        try:
            await file_watcher.start()
        except Exception:
            pass

    @app.on_event("shutdown")
    async def _shutdown_file_watcher() -> None:  # pragma: no cover - integration
        try:
            await file_watcher.stop()
        except Exception:
            pass


__all__ = ["register_lifecycle"]
