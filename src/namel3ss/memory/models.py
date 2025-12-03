"""
Memory data models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class MemoryType(str, Enum):
    CONVERSATION = "conversation"
    USER = "user"
    GLOBAL = "global"


@dataclass
class MemoryItem:
    id: str
    space: str
    type: MemoryType
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MemorySpaceConfig:
    name: str
    type: MemoryType
    retention_policy: Optional[str] = None
