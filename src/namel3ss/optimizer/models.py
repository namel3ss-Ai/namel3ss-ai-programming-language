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


class TargetType(str, Enum):
    FLOW = "flow"
    AGENT = "agent"


class SuggestionStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass
class EvaluationCase:
    id: str
    input: Dict[str, Any]
    expected: Optional[Dict[str, Any]] = None  # optional ground truth


@dataclass
class EvaluationRun:
    id: str
    target_type: TargetType
    target_name: str
    created_at: datetime
    cases: List[EvaluationCase]
    metrics_summary: Dict[str, Any]
    raw_results: List[Dict[str, Any]]


@dataclass
class Suggestion:
    id: str
    target_type: TargetType
    target_name: str
    created_at: datetime
    status: SuggestionStatus
    description: str
    change_spec: Dict[str, Any]
    evaluation_run_id: Optional[str] = None
    metadata: Dict[str, Any] = None
