"""
Lightweight tool-call observability hooks and logging helpers.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, List

from .runtime import normalize_logging_level

logger = logging.getLogger("namel3ss.tools")

_before_interceptors: List[Callable[[Any, dict[str, Any]], None]] = []
_after_interceptors: List[Callable[[Any, dict[str, Any]], None]] = []


def register_before_tool_call(func: Callable[[Any, dict[str, Any]], None]) -> None:
    _before_interceptors.append(func)


def register_after_tool_call(func: Callable[[Any, dict[str, Any]], None]) -> None:
    _after_interceptors.append(func)


def clear_tool_interceptors() -> None:
    _before_interceptors.clear()
    _after_interceptors.clear()


def _redact_headers(headers: dict[str, Any] | None) -> dict[str, Any]:
    if not headers:
        return {}
    redacted = dict(headers)
    if "Authorization" in redacted:
        redacted["Authorization"] = "***"
    return redacted


def _run_interceptors(interceptors: list[Callable[[Any, dict[str, Any]], None]], tool_cfg: Any, payload: dict[str, Any]) -> None:
    for func in list(interceptors):
        try:
            func(tool_cfg, payload)
        except Exception:  # pragma: no cover - defensive logging path
            logger.debug("Tool interceptor raised", exc_info=True)


def before_tool_call(tool_cfg: Any, request: dict[str, Any]) -> None:
    level = normalize_logging_level(getattr(tool_cfg, "logging", None))
    name = getattr(tool_cfg, "name", "<tool>")
    method = request.get("method")
    url = request.get("url")
    if level == "debug":
        logger.debug(
            "Tool %s %s %s headers=%s",
            name,
            method,
            url,
            _redact_headers(request.get("headers")),
        )
    elif level == "info":
        logger.info("Tool %s %s %s", name, method, url)
    _run_interceptors(_before_interceptors, tool_cfg, request)


def after_tool_call(tool_cfg: Any, response: dict[str, Any]) -> None:
    level = normalize_logging_level(getattr(tool_cfg, "logging", None))
    name = getattr(tool_cfg, "name", "<tool>")
    status = response.get("status")
    ok = response.get("ok", True)
    error_msg = response.get("error")
    snippet = response.get("snippet") or response.get("raw_text")
    if level == "debug":
        logger.debug(
            "Tool %s completed status=%s ok=%s error=%s snippet=%s",
            name,
            status,
            ok,
            error_msg,
            (snippet[:200] if isinstance(snippet, str) else snippet),
        )
    elif level == "info":
        if not ok:
            logger.warning("Tool %s failed status=%s error=%s", name, status, error_msg)
    elif level == "quiet":
        if not ok:
            logger.error("Tool %s failed status=%s error=%s", name, status, error_msg)
    _run_interceptors(_after_interceptors, tool_cfg, response)
