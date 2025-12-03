"""
Multi-agent team runner.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Tuple

from ..ir import IRAgent, IRProgram
from ..runtime.context import ExecutionContext, execute_ai_call_with_registry
from ..ai.router import ModelRouter
from ..ai.registry import ModelRegistry
from ..tools.registry import ToolRegistry


class AgentRole(str, Enum):
    PLANNER = "planner"
    EXECUTOR = "executor"
    VERIFIER = "verifier"
    SUMMARIZER = "summarizer"


@dataclass
class AgentMessage:
    sender: str
    role: AgentRole
    content: str


@dataclass
class TeamResult:
    messages: List[AgentMessage] = field(default_factory=list)
    summary: str | None = None


class AgentTeamRunner:
    def __init__(
        self,
        program: IRProgram,
        model_registry: ModelRegistry,
        router: ModelRouter,
        tool_registry: ToolRegistry,
    ) -> None:
        self.program = program
        self.model_registry = model_registry
        self.router = router
        self.tool_registry = tool_registry

    def run_team(
        self, agent_names: List[str], task: str, context: ExecutionContext
    ) -> TeamResult:
        messages: List[AgentMessage] = []
        if context.tracer and not context.tracer.last_trace:
            context.tracer.start_app("team")
        if context.tracer:
            context.tracer.start_team(agent_names)
        # Each agent produces a candidate response using available AI call if present.
        candidates: List[Tuple[str, str]] = []  # (agent_name, output)
        ai_call_name = next(iter(self.program.ai_calls), None)
        for idx, name in enumerate(agent_names):
            if name not in self.program.agents:
                continue
            role = list(AgentRole)[idx % len(AgentRole)]
            content = f"{role.value} processed task: {task}"
            if ai_call_name:
                ai_call = self.program.ai_calls[ai_call_name]
                output = execute_ai_call_with_registry(ai_call, self.model_registry, self.router, context)
                content = str(output)
            messages.append(AgentMessage(sender=name, role=role, content=content))
            candidates.append((name, content))
            if context.tracer:
                context.tracer.record_agent_message(
                    sender=name, role=role.value, content=content
                )
        winner = self._vote(candidates)
        summary = f"Team completed task: {task} (winner: {winner})"
        if context.tracer:
            context.tracer.record_team_vote([{"agent": a, "content": c} for a, c in candidates])
            context.tracer.end_team()
        if context.metrics:
            context.metrics.record_agent_run(provider="team")
        return TeamResult(messages=messages, summary=summary)

    def _vote(self, candidates: List[Tuple[str, str]]) -> str:
        if not candidates:
            return "none"
        # Simple heuristic: longest content wins (deterministic).
        candidates_sorted = sorted(candidates, key=lambda x: len(str(x[1])), reverse=True)
        return candidates_sorted[0][0]
