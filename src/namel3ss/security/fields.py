"""
Field-level permission masking.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Dict

from .context import SecurityContext
from .rbac import permissions_for_roles


def apply_field_permissions(
    ctx: SecurityContext,
    obj: Any,
    obj_type: str,
    field_permissions: Dict[str, Dict[str, str]],
    redaction: str = "***redacted***",
) -> Any:
    if obj_type not in field_permissions:
        return obj
    perm_map = field_permissions[obj_type]
    granted = set(permissions_for_roles(ctx.roles))

    def mask_value(value: Any, field: str) -> Any:
        required_perm = perm_map.get(field)
        if required_perm and required_perm not in granted:
            return redaction
        return value

    if is_dataclass(obj):
        data = asdict(obj)
    elif isinstance(obj, dict):
        data = dict(obj)
    else:
        return obj

    for key in list(data.keys()):
        data[key] = mask_value(data[key], key)
    return data
