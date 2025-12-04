"""
Backward-compatible API key authentication returning SecurityContext.
"""

from __future__ import annotations

from fastapi import Header, HTTPException

from .context import SecurityContext
from .models import Principal, Role
from .oauth import API_KEY_HEADER, API_KEY_ROLES


def get_principal(x_api_key: str | None = Header(default=None)) -> Principal:
    if not x_api_key or x_api_key not in API_KEY_ROLES:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    roles = API_KEY_ROLES[x_api_key]
    # pick first role for compatibility
    role_name = roles[0]
    role = Role(role_name) if role_name in Role._value2member_map_ else Role.ADMIN
    return Principal(api_key=x_api_key, role=role)
