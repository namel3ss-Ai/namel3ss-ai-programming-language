"""
Automation triggers for flows.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional
import fnmatch

from ..distributed.queue import JobQueue
from ..distributed.scheduler import JobScheduler
from ..metrics.tracker import MetricsTracker
from ..obs.tracer import Tracer
from ..secrets.manager import SecretsManager

MAX_FILE_BYTES = 10 * 1024 * 1024

@dataclass
class FlowTrigger:
    id: str
    kind: str  # "schedule" | "http" | "memory" | "file" | "agent-signal"
    flow_name: str
    config: Dict[str, Any]
    enabled: bool = True
    last_fired: Optional[datetime] = None
    next_fire_at: Optional[datetime] = None


class TriggerManager:
    def __init__(
        self,
        job_queue: JobQueue,
        secrets: Optional[SecretsManager] = None,
        tracer: Optional[Tracer] = None,
        metrics: Optional[MetricsTracker] = None,
        project_root: Optional[Path] = None,
    ) -> None:
        self.job_queue = job_queue
        self.scheduler = JobScheduler(job_queue)
        self.secrets = secrets or SecretsManager()
        self.tracer = tracer
        self.metrics = metrics
        self._triggers: Dict[str, FlowTrigger] = {}
        self._lock = asyncio.Lock()
        self.project_root = project_root or Path.cwd().resolve()
        self.file_watcher = None  # populated by runtime if available

    async def a_register_trigger(self, trigger: FlowTrigger) -> None:
        async with self._lock:
            if trigger.kind == "file":
                self._validate_file_trigger(trigger)
            self._triggers[trigger.id] = trigger
            if trigger.kind == "schedule":
                trigger.next_fire_at = self._compute_next_fire(trigger)
            if trigger.kind == "file" and self.file_watcher:
                self.file_watcher.add_trigger(trigger)

    def register_trigger(self, trigger: FlowTrigger) -> None:
        # Synchronous helper for callers without an event loop.
        if trigger.kind == "file":
            self._validate_file_trigger(trigger)
        if trigger.kind == "schedule":
            trigger.next_fire_at = self._compute_next_fire(trigger)
        self._triggers[trigger.id] = trigger
        if trigger.kind == "file" and self.file_watcher:
            self.file_watcher.add_trigger(trigger)

    async def a_fire_trigger(self, trigger_id: str, payload: dict | None = None):
        trigger = self._triggers.get(trigger_id)
        if not trigger:
            raise ValueError(f"Trigger '{trigger_id}' not found")
        if not trigger.enabled:
            return None
        return self._enqueue_trigger(trigger, payload)

    def fire_trigger(self, trigger_id: str, payload: dict | None = None):
        trigger = self._triggers.get(trigger_id)
        if not trigger:
            raise ValueError(f"Trigger '{trigger_id}' not found")
        if not trigger.enabled:
            return None
        return self._enqueue_trigger(trigger, payload)

    async def a_list_triggers(self) -> list[FlowTrigger]:
        return list(self._triggers.values())

    def list_triggers(self) -> list[FlowTrigger]:
        return list(self._triggers.values())

    def notify_memory_event(self, space: str, payload: Optional[dict] = None) -> None:
        for trigger in self._triggers.values():
            if trigger.kind != "memory" or not trigger.enabled:
                continue
            if trigger.config.get("space") and trigger.config["space"] != space:
                continue
            self._enqueue_trigger(trigger, payload or {"space": space})

    def notify_agent_signal(self, agent_name: str, payload: Optional[dict] = None) -> None:
        for trigger in self._triggers.values():
            if trigger.kind != "agent-signal" or not trigger.enabled:
                continue
            target = trigger.config.get("agent")
            if target and target != agent_name:
                continue
            self._enqueue_trigger(trigger, payload or {"agent": agent_name, "signal": "completed"})

    async def a_tick_schedules(self, now: Optional[datetime] = None) -> list:
        now = now or datetime.now(timezone.utc)
        fired = []
        async with self._lock:
            for trigger in self._triggers.values():
                if trigger.kind != "schedule" or not trigger.enabled:
                    continue
                if trigger.next_fire_at and trigger.next_fire_at <= now:
                    job = self._enqueue_trigger(trigger, {"scheduled": True})
                    fired.append(job)
                    trigger.next_fire_at = self._compute_next_fire(trigger, base_time=now)
        return fired

    def _enqueue_trigger(self, trigger: FlowTrigger, payload: dict | None = None):
        job_payload = {
            "payload": payload or {},
            "trigger_id": trigger.id,
            "trigger_kind": trigger.kind,
        }
        if trigger.config.get("code"):
            job_payload["code"] = trigger.config.get("code")
        job = self.scheduler.schedule_flow(trigger.flow_name, job_payload)
        trigger.last_fired = datetime.now(timezone.utc)
        if self.metrics:
            self.metrics.record_trigger_fire(trigger.kind)
        if self.tracer:
            self.tracer.record_flow_event(
                "flow.trigger.fire",
                {"trigger_id": trigger.id, "trigger_kind": trigger.kind, "flow": trigger.flow_name},
            )
        return job

    def notify_file_event(self, file_path: Path, event: str) -> None:
        file_path = file_path.resolve()
        for trigger in self._triggers.values():
            if trigger.kind != "file" or not trigger.enabled:
                continue
            cfg = trigger.config or {}
            base = cfg.get("path")
            if not base:
                continue
            base_path = Path(base)
            if not base_path.is_absolute():
                base_path = (self.project_root / base_path).resolve()
            if base_path not in file_path.parents and base_path != file_path.parent:
                continue
            pattern = cfg.get("pattern", "*")
            if not fnmatch.fnmatch(file_path.name, pattern):
                continue
            include_content = bool(cfg.get("include_content"))
            content = None
            if include_content and file_path.exists() and file_path.is_file():
                try:
                    size = file_path.stat().st_size
                    if size <= MAX_FILE_BYTES:
                        content = file_path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    content = None
            payload = {
                "event": event,
                "file": str(file_path),
                "content": content,
            }
            self._enqueue_trigger(trigger, payload)

    def _compute_next_fire(self, trigger: FlowTrigger, base_time: Optional[datetime] = None) -> Optional[datetime]:
        cfg = trigger.config or {}
        now = base_time or datetime.now(timezone.utc)
        if "interval_seconds" in cfg:
            try:
                interval = int(cfg["interval_seconds"])
            except (TypeError, ValueError):
                interval = 60
            return now + timedelta(seconds=interval)
        cron = cfg.get("cron")
        if cron:
            parts = cron.split()
            if len(parts) >= 1 and parts[0].startswith("*/"):
                try:
                    minutes = int(parts[0].replace("*/", ""))
                except ValueError:
                    minutes = 1
                return now + timedelta(minutes=minutes)
            if len(parts) >= 1 and parts[0].isdigit():
                minute_mark = int(parts[0])
                next_hour = now.replace(minute=minute_mark, second=0, microsecond=0)
                if next_hour <= now:
                    next_hour = next_hour + timedelta(hours=1)
                return next_hour
        return now + timedelta(minutes=1)

    def _validate_file_trigger(self, trigger: FlowTrigger) -> None:
        cfg = trigger.config or {}
        base = cfg.get("path")
        if not base:
            raise ValueError("File trigger requires a path")
        path = Path(base)
        if not path.is_absolute():
            path = (self.project_root / path).resolve()
        if self.project_root not in path.parents and self.project_root != path:
            raise ValueError("File trigger path must be within project")
        if not path.exists() or not path.is_dir():
            raise ValueError("File trigger path must be an existing directory")
        pattern = cfg.get("pattern", "*")
        # fnmatch does not throw, but ensure non-empty string
        if not isinstance(pattern, str) or not pattern:
            raise ValueError("Invalid glob pattern for file trigger")
