"""
Security models including role definitions and backward-compatible types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List


class Role(str, Enum):
    ADMIN = "admin"
    DEVELOPER = "developer"
    VIEWER = "viewer"


@dataclass
class Principal:
    api_key: str
    role: Role


@dataclass
class RoleDefinition:
    name: str
    description: str
    permissions: List[str] = field(default_factory=list)


@dataclass
class PermissionCheck:
    required_permissions: List[str]
    allow_any: bool = False
