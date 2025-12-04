"""
Shared security context models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SecurityContext:
    subject_id: Optional[str]
    app_id: Optional[str]
    tenant_id: Optional[str]
    roles: List[str] = field(default_factory=list)
    scopes: List[str] = field(default_factory=list)
    auth_scheme: str = "anonymous"
