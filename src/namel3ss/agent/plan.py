"""
Agent planning and step evaluation models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional


@dataclass
class AgentStepEvaluation:
    score: float
    verdict: Literal["accept", "retry", "stop", "escalate", "adjust_plan"]
    reasoning: str


@dataclass
class AgentStep:
    id: str = ""
    kind: Literal["tool", "ai", "subagent"] = "ai"
    target: str = ""
    description: Optional[str] = None
    max_retries: int = 0
    config: dict[str, Any] = field(default_factory=dict)
    name: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.id and self.name:
            self.id = self.name
        if not self.id:
            self.id = self.target or "step"

    @property
    def label(self) -> str:
        return self.name or self.id


@dataclass
class AgentExecutionPlan:
    steps: list[AgentStep]
    current_index: int = 0
    max_retries_per_step: int = 1
    agent_name: Optional[str] = None

    def next_step(self) -> Optional[AgentStep]:
        if self.current_index >= len(self.steps):
            return None
        step = self.steps[self.current_index]
        self.current_index += 1
        return step


@dataclass
class AgentStepResult:
    step_id: str
    input: dict[str, Any]
    output: dict[str, Any] | Any
    success: bool
    error: Optional[str]
    evaluation: Optional[AgentStepEvaluation] = None
    retries: int = 0


@dataclass
class AgentPlanResult:
    agent_name: str
    steps: list[AgentStepResult] = field(default_factory=list)
    summary: Optional[str] = None
    final_output: Any | None = None
    final_answer: Optional[str] = None
    reflection_rounds: int = 0
    critiques: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)
