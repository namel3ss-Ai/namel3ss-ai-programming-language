"""
Multi-agent team runner.
"""

from __future__ import annotations

import time
import urllib.error
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Tuple, Optional

from ..errors import ProviderCircuitOpenError, ProviderRetryError, ProviderTimeoutError
from ..ir import IRAgent, IRProgram
from ..runtime.context import ExecutionContext, execute_ai_call_with_registry
from ..ai.router import ModelRouter
from ..ai.registry import ModelRegistry
from ..tools.registry import ToolRegistry
from ..runtime.retries import get_default_retry_config, run_with_retries_and_timeout
from ..runtime.circuit_breaker import default_circuit_breaker
from ..observability.metrics import default_metrics
from .debate import DebateAgentConfig, DebateConfig, DebateEngine, DebateOutcome
from .models import AgentConfig
from .planning import AgentGoal, AgentStepPlan


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
        self._debate_engine: Optional[DebateEngine] = None

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
                provider, provider_model, provider_name = self.model_registry.resolve_provider_for_ai(ai_call)
                provider_model = provider_model or ai_call.model_name or provider_name
                provider_key = f"model:{provider_name}:{provider_model}"
                retry_config = get_default_retry_config()
                status = "success"
                start_time = time.monotonic()
                try:
                    output = run_with_retries_and_timeout(
                        lambda: execute_ai_call_with_registry(ai_call, self.model_registry, self.router, context),
                        config=retry_config,
                        error_types=(ProviderTimeoutError, urllib.error.URLError, ConnectionError, TimeoutError),
                        circuit_breaker=default_circuit_breaker,
                        provider_key=provider_key,
                    )
                    content = str(output)
                except ProviderCircuitOpenError:
                    status = "circuit_open"
                    raise
                except ProviderTimeoutError:
                    status = "timeout"
                    raise
                except ProviderRetryError:
                    status = "failure"
                    raise
                except Exception:
                    status = "failure"
                    raise
                finally:
                    duration = time.monotonic() - start_time
                    try:
                        default_metrics.record_provider_call(provider_name, provider_model, status, duration)
                        if status == "circuit_open":
                            default_metrics.record_circuit_open(provider_name)
                    except Exception:
                        pass
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

    def run_debate(
        self,
        question: str,
        agent_names: List[str],
        context: ExecutionContext,
        debate_config: Optional[DebateConfig] = None,
        agent_configs: Optional[dict[str, AgentConfig]] = None,
    ) -> DebateOutcome:
        debate_agents: List[DebateAgentConfig] = []
        for name in agent_names:
            cfg = None
            if agent_configs:
                cfg = agent_configs.get(name)
            debate_agents.append(DebateAgentConfig(id=name, config=cfg or AgentConfig()))
        if self._debate_engine is None:
            self._debate_engine = DebateEngine(
                program=self.program,
                model_registry=self.model_registry,
                tool_registry=self.tool_registry,
                router=self.router,
            )
        return self._debate_engine.run_debate(
            question=question, agents=debate_agents, context=context, config=debate_config
        )

    def plan_goal(self, goal: AgentGoal, context: ExecutionContext, agent_id: str) -> AgentStepPlan:
        runner = AgentRunner(
            program=self.program,
            model_registry=self.model_registry,
            tool_registry=self.tool_registry,
            router=self.router,
        )
        return runner.plan(goal, context, agent_id=agent_id)

    def _vote(self, candidates: List[Tuple[str, str]]) -> str:
        if not candidates:
            return "none"
        # Simple heuristic: longest content wins (deterministic).
        candidates_sorted = sorted(candidates, key=lambda x: len(str(x[1])), reverse=True)
        return candidates_sorted[0][0]
