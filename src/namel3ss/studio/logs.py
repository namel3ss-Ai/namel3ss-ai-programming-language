"""
Lightweight in-memory log buffer for Studio/daemon status streaming.
"""

from __future__ import annotations

import json
import threading
import time
from collections import deque
from typing import Deque, List, Tuple


class LogBuffer:
    def __init__(self, max_events: int = 300, mirror_stdout: bool = False) -> None:
        self.max_events = max_events
        self._events: Deque[dict] = deque(maxlen=max_events)
        self._lock = threading.Lock()
        self._seq = 0
        self._mirror_stdout = mirror_stdout

    def append(self, event: str, level: str = "info", **details) -> dict:
        with self._lock:
            self._seq += 1
            payload = {
                "id": self._seq,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "level": level,
                "event": event,
                "details": details or {},
            }
            self._events.append(payload)
        if self._mirror_stdout:
            try:
                msg = json.dumps(payload)
                print(msg)
            except Exception:
                pass
        return payload

    def history(self, limit: int | None = None) -> List[dict]:
        with self._lock:
            events = list(self._events)
        if limit is None or limit <= 0:
            return events
        return events[-limit:]

    def snapshot_after(self, last_id: int) -> Tuple[List[dict], int]:
        with self._lock:
            events = [e for e in self._events if e.get("id", 0) > last_id]
            latest = self._seq
        return events, latest


def log_event(buffer: LogBuffer, event: str, level: str = "info", **details) -> dict:
    try:
        return buffer.append(event, level=level, **details)
    except Exception:
        return {
            "id": -1,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "level": level,
            "event": event,
            "details": details,
        }
