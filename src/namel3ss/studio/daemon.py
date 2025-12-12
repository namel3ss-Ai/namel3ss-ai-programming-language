"""
Lightweight daemon state for the Studio backend.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, List, Optional

from .. import ast_nodes, ir, lexer, parser
from ..errors import Namel3ssError
from ..macros import MacroExpander, default_macro_ai_callback
from .logs import LogBuffer, log_event

try:  # pragma: no cover - optional dependency handled gracefully
    from watchdog.events import FileSystemEvent, FileSystemEventHandler
    from watchdog.observers import Observer
except Exception:  # pragma: no cover
    FileSystemEvent = object  # type: ignore
    FileSystemEventHandler = object  # type: ignore
    Observer = None  # type: ignore

_IGNORED_DIRS = {".git", ".hg", ".svn", "__pycache__", "node_modules", ".venv", "venv", "dist", "build"}


def _iter_ai_files(base: Path) -> List[Path]:
    files: list[Path] = []
    for root, dirs, names in os.walk(base):
        dirs[:] = [d for d in dirs if d not in _IGNORED_DIRS]
        for name in sorted(names):
            if name.endswith(".ai"):
                files.append(Path(root) / name)
    return sorted(files)


def _format_error(exc: Exception, path: Optional[Path] = None) -> str:
    if isinstance(exc, Namel3ssError):
        loc = ""
        if exc.line is not None:
            loc = f":{exc.line}"
            if exc.column is not None:
                loc += f":{exc.column}"
        prefix = f"{path}" if path else "program"
        return f"{prefix}{loc}: {exc.message}"
    return str(exc)


def _error_detail(exc: Exception, path: Optional[Path] = None) -> dict[str, Any] | None:
    cause = exc.__cause__ if exc.__cause__ else exc
    if hasattr(cause, "_n3_detail"):
        detail = getattr(cause, "_n3_detail")
        if isinstance(detail, dict):
            return detail
    if isinstance(cause, Namel3ssError):
        return {
            "file": str(path) if path else getattr(cause, "file", None),
            "line": getattr(cause, "line", None),
            "column": getattr(cause, "column", None),
            "message": getattr(cause, "message", str(cause)),
        }
    if isinstance(cause, FileNotFoundError):
        return {"file": str(path) if path else None, "message": str(cause)}
    return {"message": str(exc)} if str(exc) else None


@dataclass
class StudioDaemon:
    """
    Holds the in-memory IR and reloads it when source files change.
    """

    project_root: Path
    program: ir.IRProgram | None = None
    last_error: str | None = None
    last_error_detail: dict[str, Any] | None = None
    last_built_at: float | None = None
    watcher_supported: bool = True
    logs: LogBuffer = field(default_factory=LogBuffer)
    _observer: Optional[Observer] = None
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def ensure_program(self, raise_on_error: bool = True) -> ir.IRProgram | None:
        try:
            program = self._build_program()
        except Exception as exc:
            message = _format_error(exc)
            detail = _error_detail(exc)
            with self._lock:
                self.program = None
                self.last_error = message
                self.last_error_detail = detail or {"message": message}
            log_event(self.logs, "ir_reload_error", level="error", **(detail or {"message": message}))
            if raise_on_error:
                raise RuntimeError(message) from exc
            return None
        with self._lock:
            self.program = program
            self.last_error = None
            self.last_error_detail = None
            self.last_built_at = time.time()
        log_event(self.logs, "ir_reloaded", level="info", files=len(_iter_ai_files(self.project_root)))
        return program

    def start_watcher(self, debounce_seconds: float = 0.5) -> bool:
        if Observer is None or self._observer is not None:
            if Observer is None:
                self.watcher_supported = False
            return False
        handler = _AIFileEventHandler(self, debounce_seconds=debounce_seconds)
        observer = Observer()
        observer.schedule(handler, str(self.project_root), recursive=True)
        observer.start()
        self._observer = observer
        log_event(self.logs, "watcher_started", level="info", path=str(self.project_root))
        return True

    def stop_watcher(self) -> None:
        observer = self._observer
        if observer is None:
            return
        observer.stop()
        observer.join(timeout=2)
        self._observer = None
        log_event(self.logs, "watcher_stopped", level="info", path=str(self.project_root))

    def _build_program(self) -> ir.IRProgram:
        base = self.project_root.resolve()
        files = _iter_ai_files(base)
        if not files:
            raise FileNotFoundError(f"No .ai files found under {base}")
        module = ast_nodes.Module(declarations=[])
        for path in files:
            source = path.read_text(encoding="utf-8")
            try:
                tokens = lexer.Lexer(source, filename=str(path)).tokenize()
                parsed = parser.Parser(tokens).parse_module()
            except Namel3ssError as exc:
                setattr(
                    exc,
                    "_n3_detail",
                    {"file": str(path), "line": exc.line, "column": exc.column, "message": exc.message},
                )
                raise RuntimeError(_format_error(exc, path)) from exc
            module.declarations.extend(parsed.declarations)
        expanded = MacroExpander(default_macro_ai_callback).expand_module(module)
        try:
            return ir.ast_to_ir(expanded)
        except Namel3ssError as exc:
            setattr(
                exc,
                "_n3_detail",
                {"file": str(getattr(exc, "file", "") or "") or None, "line": exc.line, "column": exc.column, "message": exc.message},
            )
            raise RuntimeError(_format_error(exc)) from exc


class _AIFileEventHandler(FileSystemEventHandler):  # pragma: no cover - exercised in integration
    def __init__(self, daemon: StudioDaemon, debounce_seconds: float = 0.5) -> None:
        self.daemon = daemon
        self.debounce_seconds = debounce_seconds
        self._last_reload = 0.0

    def on_any_event(self, event: FileSystemEvent) -> None:  # type: ignore[override]
        if getattr(event, "is_directory", False):
            return
        path = Path(getattr(event, "src_path", "") or getattr(event, "dest_path", ""))
        if path.suffix != ".ai":
            return
        now = time.time()
        if now - self._last_reload < self.debounce_seconds:
            return
        self._last_reload = now
        log_event(
            self.daemon.logs,
            "watcher_event",
            level="info",
            path=str(path),
            event_type=getattr(event, "event_type", "modified"),
        )
        self.daemon.ensure_program(raise_on_error=False)
