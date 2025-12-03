"""
Optimization models for self-improving runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Dict


class OptimizationKind(str, Enum):
    FLOW_OPTIMIZATION = "flow-optimization"
    MODEL_SELECTION = "model-selection"
    PROMPT_TUNING = "prompt-tuning"
    TOOL_STRATEGY = "tool-strategy"
    MEMORY_POLICY = "memory-policy"


class OptimizationStatus(str, Enum):
    PENDING = "pending"
    APPLIED = "applied"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class OptimizationSuggestion:
    id: str
    kind: OptimizationKind
    created_at: datetime
    status: OptimizationStatus
    severity: str  # "info" | "warning" | "critical"
    title: str
    description: str
    reason: str
    target: Dict
    actions: List[Dict]
    metrics_snapshot: Dict = field(default_factory=dict)
