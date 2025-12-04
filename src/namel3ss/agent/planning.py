"""
Lightweight goal planning for agents, producing structured step plans.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .models import AgentConfig
from ..ai.router import ModelRouter
from ..runtime.context import ExecutionContext


@dataclass
class AgentGoal:
    description: str
    constraints: Dict[str, Any]


@dataclass
class AgentStepPlan:
    steps: List[str]
    rationale: str
    raw_output: str


class AgentPlanner:
    def __init__(self, router: ModelRouter, agent_config: Optional[AgentConfig] = None) -> None:
        self.router = router
        self.agent_config = agent_config or AgentConfig()

    def plan(self, goal: AgentGoal, context: ExecutionContext, agent_id: str) -> AgentStepPlan:
        prompt = self._build_prompt(goal)
        response = self.router.generate(messages=[{"role": "user", "content": prompt}])
        raw_text = self._extract_response_text(response)
        steps = self._parse_steps(raw_text)
        rationale = self._parse_rationale(raw_text)
        plan = AgentStepPlan(steps=steps, rationale=rationale, raw_output=raw_text)
        self._record_memory_plan(context, agent_id, goal, plan)
        return plan

    def _build_prompt(self, goal: AgentGoal) -> str:
        constraints_block = "\n".join(f"- {k}: {v}" for k, v in goal.constraints.items()) or "None."
        return (
            "You are a planning assistant. Create a concise, numbered list of steps to achieve the goal.\n"
            "Include a short rationale after the list under a 'Rationale:' section.\n"
            f"Goal: {goal.description}\n"
            f"Constraints:\n{constraints_block}\n"
            "Format:\n"
            "1. Step one\n"
            "2. Step two\n"
            "Rationale: Brief reasoning."
        )

    def _parse_steps(self, text: str) -> List[str]:
        lines = text.splitlines()
        steps: List[str] = []
        step_pattern = re.compile(r"^\s*(?:-|\u2022|\d+[\).\s])\s*(.+)$")
        for line in lines:
            match = step_pattern.match(line)
            if match:
                steps.append(match.group(1).strip())
        if not steps:
            # fallback: split on periods if model did not follow instructions
            parts = [part.strip() for part in text.split(".") if part.strip()]
            steps = parts[:-1] if len(parts) > 1 else parts
        return steps

    def _parse_rationale(self, text: str) -> str:
        if "Rationale:" in text:
            after = text.split("Rationale:", 1)[1]
            return after.strip()
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        return paragraphs[-1] if paragraphs else text.strip()

    def _extract_response_text(self, response: Any) -> str:
        if response is None:
            return ""
        if hasattr(response, "text"):
            try:
                return str(getattr(response, "text"))
            except Exception:
                return str(response)
        if isinstance(response, dict):
            if response.get("text") is not None:
                return str(response["text"])
            if response.get("result") is not None:
                return str(response["result"])
        if hasattr(response, "get"):
            candidate = response.get("result")
            if candidate is not None:
                return str(candidate)
        return str(response)

    def _record_memory_plan(self, context: ExecutionContext, agent_id: str, goal: AgentGoal, plan: AgentStepPlan) -> None:
        memory_engine = getattr(context, "memory_engine", None)
        if not memory_engine:
            return
        message = (
            f"agent_plan_generated | agent={agent_id} | goal={goal.description} | "
            f"steps={len(plan.steps)} | rationale={plan.rationale[:100]}"
        )
        try:
            memory_engine.record_conversation(agent_id, message, role="system")
        except Exception:
            pass
