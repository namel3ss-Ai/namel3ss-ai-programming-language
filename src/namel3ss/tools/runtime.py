"""
Helpers for tool runtime behaviour such as schema validation and error formatting.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
import uuid
import io
import urllib.parse
import urllib.request
from collections import deque, defaultdict
from decimal import Decimal
from typing import Any
from datetime import datetime, timedelta

from ..errors import Namel3ssError
from .registry import DEFAULT_TOOL_LOGGING_LEVEL, ToolResponseSchema

logger = logging.getLogger("namel3ss.tools")


class OAuthTokenCache:
    def __init__(self) -> None:
        self._cache: dict[tuple, dict[str, Any]] = {}

    def get_token(
        self,
        token_url: str,
        client_id: str,
        client_secret: str,
        scopes: list[str] | None = None,
        audience: str | None = None,
        cache_key: str | None = None,
    ) -> str:
        key = (token_url, client_id, tuple(sorted(scopes or [])), audience, cache_key or "shared")
        now = time.time()
        entry = self._cache.get(key)
        if entry and entry.get("expires_at", 0) > now + 5:
            return entry["token"]
        token, expires_in = self._fetch_token(token_url, client_id, client_secret, scopes, audience)
        ttl = expires_in or 300
        self._cache[key] = {"token": token, "expires_at": now + ttl}
        return token

    def _fetch_token(
        self,
        token_url: str,
        client_id: str,
        client_secret: str,
        scopes: list[str] | None,
        audience: str | None,
    ) -> tuple[str, float | None]:
        payload = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }
        if scopes:
            payload["scope"] = " ".join(scopes)
        if audience:
            payload["audience"] = audience
        data = urllib.parse.urlencode(payload).encode("utf-8")
        req = urllib.request.Request(
            token_url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:  # pragma: no cover - network path
            raw = resp.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except Exception as exc:  # pragma: no cover - defensive
            raise Namel3ssError(f"Failed to parse OAuth token response: {exc}")
        token = parsed.get("access_token")
        if not token:
            raise Namel3ssError("OAuth token response did not include access_token.")
        expires = parsed.get("expires_in")
        try:
            expires_val = float(expires) if expires is not None else None
        except Exception:
            expires_val = None
        return token, expires_val


oauth_token_cache = OAuthTokenCache()


def normalize_logging_level(raw: str | None) -> str:
    level = (raw or "").strip().lower()
    if level in {"debug", "info", "quiet"}:
        return level
    return DEFAULT_TOOL_LOGGING_LEVEL


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def build_jwt_token(
    tool_name: str,
    issuer: str | None,
    subject: str | None,
    audience: str | None,
    private_key: str,
    algorithm: str | None = "RS256",
    claims: dict[str, Any] | None = None,
) -> str:
    alg = (algorithm or "RS256").upper()
    now = int(time.time())
    payload: dict[str, Any] = {
        "iat": now,
        "exp": now + 300,
    }
    if issuer:
        payload["iss"] = issuer
    if subject:
        payload["sub"] = subject
    if audience:
        payload["aud"] = audience
    if claims:
        payload.update({k: v for k, v in claims.items() if k})
    header = {"alg": alg, "typ": "JWT"}
    if alg.startswith("HS"):
        digestmod = hashlib.sha256 if alg == "HS256" else None
        if digestmod is None:
            raise Namel3ssError(f"JWT algorithm '{alg}' is not supported without external libraries.")
        signing_input = f"{_b64url(json.dumps(header, separators=(',', ':'), ensure_ascii=False).encode('utf-8'))}.{_b64url(json.dumps(payload, separators=(',', ':'), ensure_ascii=False).encode('utf-8'))}"
        signature = hmac.new(private_key.encode("utf-8"), signing_input.encode("utf-8"), digestmod=digestmod).digest()
        return f"{signing_input}.{_b64url(signature)}"
    try:  # pragma: no cover - optional dependency
        import jwt  # type: ignore

        return jwt.encode(payload, private_key, algorithm=alg)
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise Namel3ssError(
            f"JWT algorithm '{alg}' requires PyJWT or compatible library. Install PyJWT to use this auth kind."
        ) from exc


def apply_auth_config(
    auth_cfg: Any,
    url: str,
    headers: dict[str, str],
    eval_value: Any,
    tool_name: str,
) -> tuple[str, dict[str, str]]:
    if not auth_cfg or not getattr(auth_cfg, "kind", None):
        return url, headers
    auth_kind = (getattr(auth_cfg, "kind", "") or "").lower()
    if auth_kind == "bearer":
        token_val = eval_value(getattr(auth_cfg, "token", None))
        if token_val is None:
            raise Namel3ssError(f'Tool "{tool_name}" auth config is incomplete (missing token).')
        headers["Authorization"] = f"Bearer {token_val}"
        return url, headers
    if auth_kind == "basic":
        username = eval_value(getattr(auth_cfg, "username", None))
        password = eval_value(getattr(auth_cfg, "password", None))
        if username is None or password is None:
            raise Namel3ssError(f'Tool "{tool_name}" auth config is incomplete (missing username/password).')
        raw = f"{username}:{password}".encode("utf-8")
        headers["Authorization"] = "Basic " + base64.b64encode(raw).decode("utf-8")
        return url, headers
    if auth_kind in {"api_key", "api-key", "apikey"}:
        location = (getattr(auth_cfg, "location", "") or "").lower()
        name = getattr(auth_cfg, "name", "") or ""
        value = eval_value(getattr(auth_cfg, "value", None))
        if not name or value is None:
            raise Namel3ssError(f'Tool "{tool_name}" auth config is incomplete (missing api_key details).')
        if location == "header":
            headers[name] = "" if value is None else str(value)
            return url, headers
        if location == "query":
            parsed = urllib.parse.urlparse(url)
            query_items = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
            query_items.append((name, "" if value is None else str(value)))
            updated = urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query_items, doseq=True)))
            return updated, headers
        raise Namel3ssError(f'Tool "{tool_name}" auth location must be "header" or "query".')
    if auth_kind == "oauth2_client_credentials":
        token_url = eval_value(getattr(auth_cfg, "token_url", None))
        client_id = eval_value(getattr(auth_cfg, "client_id", None))
        client_secret = eval_value(getattr(auth_cfg, "client_secret", None))
        audience = eval_value(getattr(auth_cfg, "audience", None))
        scopes = getattr(auth_cfg, "scopes", None) or []
        cache_mode = getattr(auth_cfg, "cache", None) or "shared"
        if not token_url or not client_id or client_secret is None:
            raise Namel3ssError(f'Tool "{tool_name}" auth config is incomplete (missing oauth2 credentials).')
        token = oauth_token_cache.get_token(
            str(token_url),
            str(client_id),
            str(client_secret),
            [str(s) for s in scopes],
            str(audience) if audience is not None else None,
            cache_key=f"{tool_name}:{cache_mode}",
        )
        headers["Authorization"] = f"Bearer {token}"
        return url, headers
    if auth_kind == "jwt":
        private_key_val = eval_value(getattr(auth_cfg, "private_key", None))
        if private_key_val is None:
            raise Namel3ssError(f'Tool "{tool_name}" auth config is incomplete (missing private_key).')
        issuer = eval_value(getattr(auth_cfg, "issuer", None))
        subject = eval_value(getattr(auth_cfg, "subject", None))
        audience = eval_value(getattr(auth_cfg, "audience", None))
        claims_raw = getattr(auth_cfg, "claims", {}) or {}
        claims: dict[str, Any] = {}
        for k, v in claims_raw.items():
            claims[k] = eval_value(v)
        token = build_jwt_token(
            tool_name,
            issuer if issuer is None else str(issuer),
            subject if subject is None else str(subject),
            audience if audience is None else str(audience),
            str(private_key_val),
            getattr(auth_cfg, "algorithm", None),
            claims,
        )
        headers["Authorization"] = f"Bearer {token}"
        return url, headers
    raise Namel3ssError(f'Tool "{tool_name}" auth kind "{auth_kind}" is not supported.')


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
