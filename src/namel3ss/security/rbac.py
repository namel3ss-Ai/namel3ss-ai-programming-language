"""
Role and permission utilities.
"""

from __future__ import annotations

from typing import Dict, List

from fastapi import Depends, HTTPException

from .context import SecurityContext
from .models import PermissionCheck, RoleDefinition
from .oauth import get_oauth_context


ROLE_DEFINITIONS: Dict[str, RoleDefinition] = {
    "admin": RoleDefinition(
        name="admin",
        description="Full access",
        permissions=[
            "flows:read",
            "flows:write",
            "memory:read",
            "memory:write",
            "memory:content:read",
            "memory:metadata:read_sensitive",
            "agents:run",
            "metrics:read",
            "rag:read",
            "rag:write",
            "diagnostics:read",
            "optimizer:run",
            "optimizer:read",
            "ecosystem:read",
        ],
    ),
    "developer": RoleDefinition(
        name="developer",
        description="Read/write flows and memory",
        permissions=[
            "flows:read",
            "flows:write",
            "memory:read",
            "memory:write",
            "memory:content:read",
            "agents:run",
            "metrics:read",
            "rag:read",
            "optimizer:run",
            "optimizer:read",
            "ecosystem:read",
        ],
    ),
    "viewer": RoleDefinition(
        name="viewer",
        description="Read-only access",
        permissions=["flows:read", "memory:read", "metrics:read", "rag:read", "optimizer:read", "ecosystem:read"],
    ),
}


def permissions_for_roles(roles: List[str]) -> List[str]:
    perms: List[str] = []
    for role in roles:
        if role in ROLE_DEFINITIONS:
            perms.extend(ROLE_DEFINITIONS[role].permissions)
    return sorted(set(perms))


def can_run_app(role: str) -> bool:
    return role in {"admin", "developer", "viewer"}


def can_run_flow(role: str) -> bool:
    return role in {"admin", "developer"}


def can_view_traces(role: str) -> bool:
    return role in {"admin", "developer"}


def can_view_pages(role: str) -> bool:
    return role in {"admin", "developer", "viewer"}


def require_permissions(required: List[str], allow_any: bool = False):
    def dependency(ctx: SecurityContext = Depends(get_oauth_context)):
        granted = set(permissions_for_roles(ctx.roles))
        need = set(required)
        if allow_any:
            if granted.intersection(need):
                return ctx
        else:
            if need.issubset(granted):
                return ctx
        raise HTTPException(status_code=403, detail="Forbidden")

    return dependency
