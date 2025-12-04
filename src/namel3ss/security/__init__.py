"""
Security subsystem for Namel3ss.
"""

from .context import SecurityContext
from .oauth import OAuthConfig, get_oauth_context, API_KEY_HEADER
from .rbac import (
    ROLE_DEFINITIONS,
    require_permissions,
    permissions_for_roles,
    can_run_app,
    can_run_flow,
    can_view_traces,
    can_view_pages,
)
from .fields import apply_field_permissions
from .quotas import QuotaConfig, InMemoryQuotaTracker, quota_dependency
from .auth import get_principal
from .models import Principal, Role

__all__ = [
    "SecurityContext",
    "OAuthConfig",
    "get_oauth_context",
    "ROLE_DEFINITIONS",
    "require_permissions",
    "permissions_for_roles",
    "can_run_app",
    "can_run_flow",
    "can_view_traces",
    "can_view_pages",
    "apply_field_permissions",
    "QuotaConfig",
    "InMemoryQuotaTracker",
    "quota_dependency",
    "get_principal",
    "API_KEY_HEADER",
    "Principal",
    "Role",
]
