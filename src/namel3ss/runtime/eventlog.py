from __future__ import annotations

import datetime
from typing import Any, Dict

from ..errors import Namel3ssError


class EventLogger:
    """
    Minimal structured event logger that writes into the event_log frame.
    Logging must never crash the caller; failures are turned into warnings/errors that can be surfaced separately.
    """

    def __init__(self, frames, session_id: str | None = None):
        self.frames = frames
        self.session_id = session_id or "default"
        # Ensure the event_log frame exists
        if "event_log" not in getattr(self.frames, "frames", {}):
            try:
                from ..ir import IRFrame

                self.frames.register("event_log", IRFrame(name="event_log", backend="memory", table="event_log"))
            except Exception:
                pass

    def log(self, event: Dict[str, Any]) -> None:
        row = dict(event)
        row.setdefault("timestamp", datetime.datetime.utcnow().isoformat() + "Z")
        row.setdefault("session_id", self.session_id)
        try:
            self.frames.insert("event_log", row)
        except Exception as exc:  # pragma: no cover - defensive
            # Logging must not crash primary execution; surface as best-effort diagnostic.
            self.last_error = Namel3ssError(f"N3F-900: Failed to write event log: {exc}")
