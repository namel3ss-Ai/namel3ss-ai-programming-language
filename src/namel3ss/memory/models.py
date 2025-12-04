"""
Memory data models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
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


@dataclass
class MemoryNamespace:
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    agent_id: Optional[str] = None

    def key(self) -> tuple:
        return (self.tenant_id, self.user_id, self.agent_id)


@dataclass
class EpisodicMemoryRecord:
    id: str
    namespace: MemoryNamespace
    timestamp: datetime
    kind: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SemanticMemoryRecord:
    id: str
    namespace: MemoryNamespace
    created_at: datetime
    source_range: Dict[str, Any]
    summary: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RetentionPolicy:
    max_episodes_per_namespace: Optional[int] = None
    max_age_days: Optional[int] = None
