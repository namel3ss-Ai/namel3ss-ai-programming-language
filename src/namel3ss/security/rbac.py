"""
RBAC utilities.
"""

from __future__ import annotations

from .models import Role


def can_run_app(role: Role) -> bool:
    return role in {Role.ADMIN, Role.DEVELOPER, Role.VIEWER}


def can_run_flow(role: Role) -> bool:
    return role in {Role.ADMIN, Role.DEVELOPER}


def can_view_traces(role: Role) -> bool:
    return role in {Role.ADMIN, Role.DEVELOPER}


def can_view_pages(role: Role) -> bool:
    return role in {Role.ADMIN, Role.DEVELOPER, Role.VIEWER}
