"""
Tracing models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class AITrace:
    model_name: str
    prompt: str
    response_preview: str
    cost_tokens: Optional[int] = None
    provider_name: Optional[str] = None
    logical_model_name: Optional[str] = None


@dataclass
class PageTrace:
    page_name: str
    ai_calls: List[AITrace] = field(default_factory=list)
    agents: List["AgentTrace"] = field(default_factory=list)
    ui_section_count: Optional[int] = None


@dataclass
class AppTrace:
    app_name: str
    pages: List[PageTrace] = field(default_factory=list)
    flows: List["FlowTrace"] = field(default_factory=list)
    teams: List["TeamTrace"] = field(default_factory=list)
    rag_queries: List["RAGTrace"] = field(default_factory=list)
    role: Optional[str] = None


@dataclass
class AgentStepTrace:
    step_name: str
    kind: str
    target: str
    success: bool
    retries: int
    output_preview: Optional[str] = None
    evaluation_score: Optional[float] = None
    verdict: Optional[str] = None


@dataclass
class AgentTrace:
    agent_name: str
    steps: List[AgentStepTrace] = field(default_factory=list)
    events: List[Any] = field(default_factory=list)
    summary: Optional[str] = None


@dataclass
class FlowStepTrace:
    step_name: str
    kind: str
    target: str
    success: bool
    output_preview: Optional[str] = None
    node_id: Optional[str] = None
    handled: Optional[bool] = None


@dataclass
class FlowTrace:
    flow_name: str
    steps: List[FlowStepTrace] = field(default_factory=list)
    events: List[Any] = field(default_factory=list)


@dataclass
class JobTrace:
    job_id: str
    job_type: str
    target: str
    status: str
    steps: List[Any] = field(default_factory=list)


@dataclass
class TeamTrace:
    agents: List[str]
    messages: List[Any] = field(default_factory=list)
    votes: List[Any] = field(default_factory=list)


@dataclass
class RAGTrace:
    query: str
    indexes: List[str]
    hybrid: Optional[bool] = None
    result_count: int = 0
