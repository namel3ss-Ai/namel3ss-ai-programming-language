"""Health and basic Studio status/log routes."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse


def build_health_router(
    log_buffer,
    log_event,
    studio_status_payload,
    project_root,
    studio_static_dir,
    studio_config_files,
) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    def health() -> Dict[str, str]:
        log_event(log_buffer, "health_ping", level="info")
        return {"status": "ok"}

    @router.get("/api/studio/status")
    def api_studio_status() -> Dict[str, Any]:
        try:
            payload = studio_status_payload()
            log_event(log_buffer, "status_requested", level="info")
            return payload
        except Exception as exc:  # pragma: no cover - should never raise
            base = project_root()
            log_event(log_buffer, "status_error", level="error", message=str(exc))
            return {
                "project_root": str(base),
                "ai_files": 0,
                "ai_file_paths": [],
                "watcher_active": False,
                "watcher_supported": False,
                "ir_status": "error",
                "ir_error": {"message": str(exc)},
                "studio_static_available": bool(studio_static_dir and (studio_static_dir / "index.html").exists()),
                "config_file_found": any((base / name).exists() for name in studio_config_files),
            }

    @router.get("/api/studio/logs/stream")
    def api_studio_logs_stream(request: Request, once: bool = False):
        # Minimal SSE-like stream using NDJSON for compatibility.
        async def event_generator():
            last_id = 0
            history = log_buffer.history()
            for entry in history:
                last_id = entry.get("id", last_id)
                yield json.dumps(entry) + "\n"
            if once:
                return
            while True:
                if await request.is_disconnected():
                    break
                events, last_id = log_buffer.snapshot_after(last_id)
                if events:
                    for entry in events:
                        yield json.dumps(entry) + "\n"
                await asyncio.sleep(0.5)

        return StreamingResponse(event_generator(), media_type="text/plain")

    return router


__all__ = ["build_health_router"]
