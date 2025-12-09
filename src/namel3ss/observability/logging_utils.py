from __future__ import annotations

import os
from typing import Any, Dict

_SENSITIVE_KEYS = {"email", "phone", "authorization", "access_token", "password", "secret", "token"}


def _env_bool(name: str, default: bool = True) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "yes", "on"}


def redact_prompt(prompt: str) -> str:
    if not _env_bool("N3_LOG_REDACT_PROMPTS", True):
        return prompt
    if not prompt:
        return prompt
    return "[REDACTED]"


def redact_metadata(meta: Dict[str, Any]) -> Dict[str, Any]:
    if not _env_bool("N3_LOG_REDACT_METADATA", True):
        return dict(meta)
    redacted: Dict[str, Any] = {}
    for key, value in meta.items():
        key_lower = key.lower()
        if key_lower in _SENSITIVE_KEYS:
            redacted[key] = "[REDACTED]"
        else:
            redacted[key] = value
    return redacted


def redact_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply prompt/metadata redaction to event payloads before logging.
    """

    sanitized = dict(event)
    for key in ("prompt", "content", "message", "input"):
        if key in sanitized and isinstance(sanitized[key], str):
            sanitized[key] = redact_prompt(sanitized[key])
    if "metadata" in sanitized and isinstance(sanitized["metadata"], dict):
        sanitized["metadata"] = redact_metadata(sanitized["metadata"])
    return sanitized

