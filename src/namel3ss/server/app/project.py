"""Project-specific helpers: parsing, static assets, and manifest helpers."""

from __future__ import annotations

import os
import importlib.resources as resources
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Dict, Tuple

from fastapi import HTTPException

from ... import ir, lexer, parser
from ...runtime.engine import Engine
from ...ui.manifest import build_ui_manifest
from ...studio.logs import LogBuffer, log_event
from ...plugins.registry import PluginRegistry
from ...flows.triggers import TriggerManager
from ...metrics.tracker import MetricsTracker
from ...errors import Namel3ssError

_APPLE_MARKERS = ("Canvas", "Ask Studio", "Command Palette", "Presentation")
_LEGACY_MARKER = "Minimal Developer Console"
BASE_DIR = Path(__file__).resolve().parents[3]
STUDIO_CONFIG_FILES = ("namel3ss.config.json", "namel3ss.toml", "namel3ss.config.toml")


def is_apple_studio_dir(candidate: Path) -> bool:
    """Return True when the candidate directory contains the Apple-style Studio UI."""
    index = candidate / "index.html"
    if not index.exists():
        return False
    try:
        text = index.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False
    if _LEGACY_MARKER in text:
        return False
    return all(marker in text for marker in _APPLE_MARKERS)


def resolve_studio_static_dir() -> Path | None:
    """
    Prefer the Apple-style Studio assets; bias toward the source tree when present
    to avoid stale installed copies during development, and fall back to the
    packaged assets when they look valid.
    """
    candidates: list[Path] = []
    source_dir = BASE_DIR / "src" / "namel3ss" / "studio_static"
    if source_dir.exists():
        candidates.append(source_dir)
    try:
        candidate = resources.files("namel3ss") / "studio_static"
        if candidate.is_dir():
            pkg_path = Path(candidate)
            if pkg_path not in candidates:
                candidates.append(pkg_path)
    except Exception:
        # Fall back to workspace copy below.
        pass
    valid = [candidate for candidate in candidates if is_apple_studio_dir(candidate)]
    if valid:
        return valid[0]
    # Do not fall back to legacy/minimal consoles; we prefer to leave Studio
    # unavailable rather than serve the wrong UI.
    return None


STUDIO_STATIC_DIR = resolve_studio_static_dir()


def serialize_stream_event(evt) -> dict[str, Any]:
    mapping: dict[str, Any] = {
        "flow": evt.get("flow"),
        "step": evt.get("step"),
        "channel": evt.get("channel"),
        "role": evt.get("role"),
        "label": evt.get("label"),
        "mode": evt.get("mode"),
    }
    kind = evt.get("kind")
    if kind == "chunk":
        mapping["event"] = "ai_chunk"
        mapping["delta"] = evt.get("delta") or ""
    elif kind == "done":
        mapping["event"] = "ai_done"
        mapping["full"] = evt.get("full") or ""
    elif kind == "error":
        mapping["event"] = "flow_error"
        mapping["error"] = evt.get("error") or ""
        if evt.get("code") is not None:
            mapping["code"] = evt.get("code")
    elif kind == "flow_done":
        mapping["event"] = "flow_done"
        mapping["success"] = bool(evt.get("success", True))
        if "result" in evt and evt.get("result") is not None:
            mapping["result"] = evt.get("result")
    elif kind == "state_change":
        mapping["event"] = "state_change"
        mapping["path"] = evt.get("path")
        if "old_value" in evt:
            mapping["old_value"] = evt.get("old_value")
        if "new_value" in evt:
            mapping["new_value"] = evt.get("new_value")
    else:
        mapping["event"] = kind or "unknown"
    return {
        k: v
        for k, v in mapping.items()
        if v is not None or k in {"delta", "full", "event", "old_value", "new_value"}
    }


def parse_source_to_ast(source: str) -> Dict[str, Any]:
    tokens = lexer.Lexer(source).tokenize()
    module = parser.Parser(tokens).parse_module()
    return asdict(module)


def parse_source_to_ir(source: str) -> ir.IRProgram:
    tokens = lexer.Lexer(source).tokenize()
    module = parser.Parser(tokens).parse_module()
    return ir.ast_to_ir(module)


def build_project_helpers(
    project_root: Path,
    get_cached_program: Callable[[], ir.IRProgram | None],
    set_cached_program: Callable[[ir.IRProgram | None], None],
    log_event_fn: Callable[..., Any],
    log_buffer: LogBuffer,
    ignored_dirs: set[str],
    metrics_tracker: MetricsTracker,
    trigger_manager: TriggerManager,
    plugin_registry: PluginRegistry,
    daemon_state: Any | None,
) -> Tuple[
    Callable[[Path], list[Path]],
    Callable[[], Dict[str, Any]],
    Callable[[], Dict[str, Any]],
    Callable[[], ir.IRProgram],
    Callable[[ir.IRProgram | None], Engine],
]:
    def _iter_ai_files(base: Path) -> list[Path]:
        files: list[Path] = []
        for root, dirs, file_names in os.walk(base):
            dirs[:] = [d for d in dirs if d not in ignored_dirs]
            for fname in sorted(file_names):
                if not fname.endswith(".ai"):
                    continue
                files.append(Path(root) / fname)
        return files

    def _studio_status_payload() -> Dict[str, Any]:
        base = project_root
        ai_files = _iter_ai_files(base)
        ai_paths = [str(p.relative_to(base)).replace("\\", "/") for p in ai_files]
        studio_static_available = bool(STUDIO_STATIC_DIR and (STUDIO_STATIC_DIR / "index.html").exists())
        config_file_found = any((base / name).exists() for name in STUDIO_CONFIG_FILES)
        payload: Dict[str, Any] = {
            "project_root": str(base),
            "ai_files": len(ai_files),
            "ai_file_paths": ai_paths,
            "watcher_active": False,
            "watcher_supported": True,
            "ir_status": "unknown",
            "ir_error": None,
            "studio_static_available": studio_static_available,
            "config_file_found": config_file_found,
        }
        if daemon_state is not None:
            payload["watcher_active"] = bool(getattr(daemon_state, "_observer", None))
            payload["watcher_supported"] = getattr(daemon_state, "watcher_supported", True)
            cached_program = get_cached_program()
            last_error = getattr(daemon_state, "last_error", None)
            last_error_detail = getattr(daemon_state, "last_error_detail", None)
            if cached_program:
                payload["ir_status"] = "valid"
            elif last_error:
                payload["ir_status"] = "error"
                payload["ir_error"] = last_error_detail or {"message": last_error}
            elif not ai_files:
                payload["ir_status"] = "error"
                payload["ir_error"] = {"message": "No .ai files found"}
        else:
            payload["watcher_active"] = False
            payload["watcher_supported"] = True
            if not ai_files:
                payload["ir_status"] = "error"
                payload["ir_error"] = {"message": "No .ai files found"}
            else:
                try:
                    combined = "\n\n".join(p.read_text(encoding="utf-8") for p in ai_files)
                    Engine._load_program(combined, filename=str(base / "project.ai"))
                    payload["ir_status"] = "valid"
                except Namel3ssError as exc:
                    payload["ir_status"] = "error"
                    payload["ir_error"] = {
                        k: v
                        for k, v in {
                            "message": getattr(exc, "message", str(exc)),
                            "file": getattr(exc, "filename", None) or getattr(exc, "file", None),
                            "line": getattr(exc, "line", None),
                            "column": getattr(exc, "column", None),
                        }.items()
                        if v is not None
                    }
                except Exception as exc:  # pragma: no cover - defensive
                    payload["ir_status"] = "error"
                    payload["ir_error"] = {"message": str(exc)}
                else:
                    log_event_fn(log_buffer, "ir_reloaded", level="info", files=len(ai_files))
        return payload

    def _project_ui_manifest() -> Dict[str, Any]:
        pages: list[dict[str, Any]] = []
        components: list[dict[str, Any]] = []
        theme: dict[str, Any] = {}
        base = project_root
        for path in _iter_ai_files(base):
            try:
                program = Engine._load_program(path.read_text(encoding="utf-8"), filename=str(path))
                mf = build_ui_manifest(program)
            except Exception:
                continue
            if not theme and mf.get("theme"):
                theme = mf["theme"]
            existing_components = {c["name"] for c in components}
            for comp in mf.get("components", []):
                if comp["name"] not in existing_components:
                    components.append(comp)
            for page in mf.get("pages", []):
                pcopy = dict(page)
                pcopy["source_path"] = str(path.relative_to(base)).replace("\\", "/")

                def _set_source(el):
                    if isinstance(el, dict):
                        el.setdefault("source_path", pcopy["source_path"])
                        for child in el.get("layout", []):
                            _set_source(child)
                        for block in el.get("when", []):
                            _set_source(block)
                        for block in el.get("otherwise", []):
                            _set_source(block)
                    return el

                _set_source(pcopy)
                pages.append(pcopy)
        return {
            "ui_manifest_version": "1",
            "pages": pages,
            "components": components,
            "theme": theme,
        }

    def _project_program() -> ir.IRProgram:
        cached_program = get_cached_program()
        if cached_program is not None:
            return cached_program
        base = project_root
        sources: list[str] = []
        for path in _iter_ai_files(base):
            sources.append(path.read_text(encoding="utf-8"))
        if not sources:
            raise HTTPException(status_code=400, detail="No .ai files found")
        combined = "\n\n".join(sources)
        try:
            program = Engine._load_program(combined, filename=str(base / "project.ai"))
            set_cached_program(program)
            log_event_fn(log_buffer, "ir_reloaded", level="info", files=len(sources))
            return program
        except Exception as exc:
            log_event_fn(log_buffer, "ir_reload_error", level="error", message=str(exc))
            raise

    def _build_project_engine(program: ir.IRProgram | None = None) -> Engine:
        prog = program or _project_program()
        return Engine(
            prog,
            metrics_tracker=metrics_tracker,
            trigger_manager=trigger_manager,
            plugin_registry=plugin_registry,
        )

    return (
        _iter_ai_files,
        _studio_status_payload,
        _project_ui_manifest,
        _project_program,
        _build_project_engine,
    )


__all__ = [
    "BASE_DIR",
    "STUDIO_CONFIG_FILES",
    "STUDIO_STATIC_DIR",
    "build_project_helpers",
    "is_apple_studio_dir",
    "parse_source_to_ast",
    "parse_source_to_ir",
    "resolve_studio_static_dir",
    "serialize_stream_event",
]
