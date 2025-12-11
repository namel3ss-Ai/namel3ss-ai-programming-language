"""
Helpers for tool runtime behaviour such as schema validation and error formatting.
"""

from __future__ import annotations

import logging
import time
import uuid
import io
from collections import deque, defaultdict
from decimal import Decimal
from typing import Any

from .registry import DEFAULT_TOOL_LOGGING_LEVEL, ToolResponseSchema

logger = logging.getLogger("namel3ss.tools")


def normalize_logging_level(raw: str | None) -> str:
    level = (raw or "").strip().lower()
    if level in {"debug", "info", "quiet"}:
        return level
    return DEFAULT_TOOL_LOGGING_LEVEL


def _type_name(value: Any) -> str:
    return type(value).__name__


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float, Decimal)) and not isinstance(value, bool)


def validate_response_schema(schema: ToolResponseSchema | None, data: Any) -> tuple[bool, str | None]:
    """
    Validate a parsed response body against a minimal schema definition.

    Returns (ok, error_message).
    """
    if schema is None:
        return True, None
    expected = (schema.type or "").lower()
    if expected == "object":
        if not isinstance(data, dict):
            return False, f"expected object but got { _type_name(data) }"
        for field in schema.required or []:
            if field not in data:
                return False, f"missing required field '{field}'"
        for key, prop_type in (schema.properties or {}).items():
            if key not in data:
                continue
            ok, err = _validate_simple_type(prop_type, data.get(key))
            if not ok:
                return False, f"field '{key}' {err}"
        return True, None
    if expected == "array":
        if not isinstance(data, list):
            return False, f"expected array but got { _type_name(data) }"
        return True, None
    if expected == "string":
        return _validate_simple_type("string", data)
    if expected == "number":
        return _validate_simple_type("number", data)
    if expected == "boolean":
        return _validate_simple_type("boolean", data)
    return False, f"unsupported schema type '{schema.type}'"


def _validate_simple_type(expected: str, value: Any) -> tuple[bool, str | None]:
    if expected == "string":
        if isinstance(value, str):
            return True, None
        return False, f"expected string but got {_type_name(value)}"
    if expected == "number":
        if _is_number(value):
            return True, None
        return False, f"expected number but got {_type_name(value)}"
    if expected == "boolean":
        if isinstance(value, bool):
            return True, None
        return False, f"expected boolean but got {_type_name(value)}"
    if expected == "object":
        if isinstance(value, dict):
            return True, None
        return False, f"expected object but got {_type_name(value)}"
    if expected == "array":
        if isinstance(value, list):
            return True, None
        return False, f"expected array but got {_type_name(value)}"
    return False, f"unsupported schema type '{expected}'"


def format_tool_error(
    tool_name: str,
    method: str,
    url: str,
    status: int | None = None,
    reason: str | None = None,
    raw_text: str | None = None,
) -> str:
    status_part = f"status {status}" if status is not None else "no status"
    prefix = f'Tool "{tool_name}" {method} {url}'
    snippet = ""
    if raw_text:
        flat = " ".join(raw_text.strip().split())
        if flat:
            snippet = f' Response snippet: "{flat[:200]}"'
    if reason:
        return f"{prefix} failed with {status_part}: {reason}{snippet}"
    return f"{prefix} failed with {status_part}{snippet}"


def build_tool_result(
    tool_cfg: Any,
    method: str,
    url: str,
    status: int | None,
    parsed_body: Any,
    headers: dict[str, str],
    raw_text: str | None,
) -> dict[str, Any]:
    ok = 200 <= (status or 0) < 300
    error_msg: str | None = None
    schema = getattr(tool_cfg, "response_schema", None)
    tool_name = getattr(tool_cfg, "name", "tool")
    if ok and schema:
        valid, schema_error = validate_response_schema(schema, parsed_body)
        if not valid:
            ok = False
            error_msg = format_tool_error(
                tool_name,
                method,
                url,
                status,
                f"Response schema validation failed: {schema_error}",
                raw_text,
            )
    if not ok and error_msg is None:
        reason = f"HTTP {status}" if status is not None else "HTTP error"
        error_msg = format_tool_error(tool_name, method, url, status, reason, raw_text)
    result: dict[str, Any] = {
        "ok": ok,
        "status": status,
        "data": parsed_body,
        "headers": headers,
    }
    if error_msg:
        result["error"] = error_msg
    return result


class RateLimiter:
    def __init__(self) -> None:
        self._per_tool_minute: defaultdict[str, deque[float]] = defaultdict(deque)
        self._per_tool_second: defaultdict[str, deque[float]] = defaultdict(deque)

    def allow(self, tool_name: str, max_per_minute: int | None, max_per_second: int | None, burst: int | None) -> bool:
        now = time.time()
        burst_limit = burst
        if max_per_minute is not None:
            dq = self._per_tool_minute[tool_name]
            window_start = now - 60.0
            while dq and dq[0] < window_start:
                dq.popleft()
            limit = max_per_minute
            if burst_limit is not None:
                limit = max(burst_limit, limit)
            if len(dq) >= limit:
                return False
            dq.append(now)
        if max_per_second is not None:
            dq_s = self._per_tool_second[tool_name]
            window_start_s = now - 1.0
            while dq_s and dq_s[0] < window_start_s:
                dq_s.popleft()
            limit_s = max_per_second
            if burst_limit is not None:
                limit_s = max(burst_limit, limit_s)
            if len(dq_s) >= limit_s:
                return False
            dq_s.append(now)
        return True

    def reset(self, tool_name: str | None = None) -> None:
        if tool_name is None:
            self._per_tool_minute.clear()
            self._per_tool_second.clear()
            return
        self._per_tool_minute.pop(tool_name, None)
        self._per_tool_second.pop(tool_name, None)


rate_limiter = RateLimiter()


def encode_query_items(key: str, value: Any, mode: str | None) -> list[tuple[str, str]]:
    if value is None:
        return []
    effective_mode = (mode or "repeat").lower()
    if isinstance(value, (list, tuple)):
        vals = value
    else:
        vals = [value]
    if effective_mode == "csv":
        flat = ",".join("" if v is None else str(v) for v in vals)
        return [(key, flat)]
    encoded: list[tuple[str, str]] = []
    for item in vals:
        encoded_key = key
        if effective_mode == "brackets":
            encoded_key = f"{key}[]"
        encoded.append((encoded_key, "" if item is None else str(item)))
    return encoded


def build_multipart_body(fields: dict[str, Any]) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    body = io.BytesIO()
    for name, value in (fields or {}).items():
        if value is None:
            continue
        body.write(f"--{boundary}\r\n".encode("utf-8"))
        filename = None
        data_bytes: bytes
        if hasattr(value, "read"):
            content = value.read()
            data_bytes = content if isinstance(content, (bytes, bytearray)) else str(content).encode("utf-8")
            filename = getattr(value, "name", name)
        elif isinstance(value, (bytes, bytearray)):
            data_bytes = bytes(value)
            filename = name
        else:
            data_bytes = str(value).encode("utf-8")
        if filename:
            body.write(f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode("utf-8"))
            body.write(b"Content-Type: application/octet-stream\r\n\r\n")
        else:
            body.write(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        body.write(data_bytes)
        body.write(b"\r\n")
    body.write(f"--{boundary}--\r\n".encode("utf-8"))
    content_type = f"multipart/form-data; boundary={boundary}"
    return body.getvalue(), content_type
