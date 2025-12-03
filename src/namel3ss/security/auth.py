"""
API key authentication for FastAPI endpoints.
"""

from __future__ import annotations

from fastapi import Header, HTTPException

from .models import Principal, Role

API_KEY_HEADER = "X-API-Key"

KNOWN_KEYS = {
    "admin-key": Role.ADMIN,
    "dev-key": Role.DEVELOPER,
    "viewer-key": Role.VIEWER,
}


def get_principal(x_api_key: str | None = Header(default=None)) -> Principal:
    if not x_api_key or x_api_key not in KNOWN_KEYS:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return Principal(api_key=x_api_key, role=KNOWN_KEYS[x_api_key])
