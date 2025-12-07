"""
Simple file watcher for file-based flow triggers.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Dict


class FileWatcher:
    def __init__(self, trigger_manager, project_root: Path, poll_interval: float = 1.0) -> None:
        self.trigger_manager = trigger_manager
        self.project_root = project_root.resolve()
        self.poll_interval = poll_interval
        self._trigger_files: Dict[str, Dict[Path, float]] = {}
        self._triggers: Dict[str, object] = {}
        self._task: asyncio.Task | None = None
        self._running = False

    def add_trigger(self, trigger) -> None:
        if trigger.id in self._triggers:
            return
        self._triggers[trigger.id] = trigger
        self._trigger_files[trigger.id] = {}

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except Exception:  # pragma: no cover - best effort shutdown
                pass

    async def _run(self) -> None:
        while self._running:
            await self.poll_once()
            await asyncio.sleep(self.poll_interval)

    async def poll_once(self) -> None:
        for trigger_id, trigger in list(self._triggers.items()):
            cfg = trigger.config or {}
            base = Path(cfg.get("path", "."))
            if not base.is_absolute():
                base = (self.project_root / base).resolve()
            pattern = cfg.get("pattern", "*")
            known = self._trigger_files.get(trigger_id, {})
            seen: Dict[Path, float] = {}
            if not base.exists() or not base.is_dir():
                continue
            for file_path in base.glob(pattern):
                if file_path.is_dir():
                    continue
                try:
                    mtime = file_path.stat().st_mtime
                except OSError:
                    continue
                prev = known.get(file_path)
                if prev is None:
                    self.trigger_manager.notify_file_event(file_path, "created")
                elif mtime > prev:
                    self.trigger_manager.notify_file_event(file_path, "modified")
                seen[file_path] = mtime
            # deletions
            for old_path in list(known.keys()):
                if old_path not in seen and not old_path.exists():
                    self.trigger_manager.notify_file_event(old_path, "deleted")
            self._trigger_files[trigger_id] = seen

    def simulate_event(self, file_path: Path, event: str) -> None:
        self.trigger_manager.notify_file_event(file_path, event)
