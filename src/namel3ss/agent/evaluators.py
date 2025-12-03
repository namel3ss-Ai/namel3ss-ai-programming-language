"""
Agent step evaluators: deterministic and OpenAI-backed.
"""

from __future__ import annotations

from typing import Protocol, Any

from .plan import AgentStepEvaluation, AgentStepResult
from ..ai.router import ModelRouter
from ..ai.registry import ModelRegistry
from ..secrets.manager import SecretsManager


class AgentStepEvaluator(Protocol):
    def evaluate(self, step_result: AgentStepResult, context) -> AgentStepEvaluation:
        ...


class DeterministicEvaluator:
    """
    Fast, deterministic evaluator for tests/CI and local runs without network.
    """

    def __init__(self, max_retries: int = 1, budget_cost: float = 5.0) -> None:
        self.max_retries = max_retries
        self.budget_cost = budget_cost

    def evaluate(self, step_result: AgentStepResult, context) -> AgentStepEvaluation:
        # Budget-aware decision based on metrics snapshot.
        if context.metrics:
            total_cost = context.metrics.snapshot().get("total_cost", 0.0)
            if total_cost >= self.budget_cost:
                return AgentStepEvaluation(
                    score=0.0,
                    verdict="stop",
                    reasoning="Budget exceeded; stopping plan.",
                )
        if step_result.success:
            return AgentStepEvaluation(score=0.9, verdict="accept", reasoning="Step succeeded.")
        if step_result.retries >= self.max_retries:
            return AgentStepEvaluation(
                score=0.1, verdict="stop", reasoning="Retries exhausted for this step."
            )
        return AgentStepEvaluation(score=0.2, verdict="retry", reasoning="Attempt failed, retrying.")


class OpenAIEvaluator:
    """
    Uses the existing AI provider registry + router to score/evaluate a step.
    Kept sync for simplicity; provider.invoke is synchronous in current code.
    """

    def __init__(
        self,
        registry: ModelRegistry,
        router: ModelRouter,
        secrets: SecretsManager,
        logical_model: str | None = None,
    ) -> None:
        self.registry = registry
        self.router = router
        self.logical_model = logical_model
        self.secrets = secrets

    def evaluate(self, step_result: AgentStepResult, context) -> AgentStepEvaluation:
        try:
            selection = self.router.select_model(logical_name=self.logical_model)
            cfg = self.registry.get_model_config(selection.model_name)
            provider = self.registry.get_provider_for_model(selection.model_name)
            prompt = self._build_prompt(step_result)
            resp = provider.invoke(
                messages=[{"role": "user", "content": prompt}],
                model=cfg.model or selection.model_name,
            )
            reasoning = str(resp.get("result", ""))[:200]
            # Simple heuristic: look for "retry"/"stop" tokens
            verdict: str = "accept"
            score = 0.8
            if "retry" in reasoning.lower():
                verdict = "retry"
                score = 0.4
            if "stop" in reasoning.lower():
                verdict = "stop"
                score = 0.1
            return AgentStepEvaluation(score=score, verdict=verdict, reasoning=reasoning)
        except Exception:
            # Fall back to deterministic behaviour on errors.
            return DeterministicEvaluator().evaluate(step_result, context)

    def _build_prompt(self, step_result: AgentStepResult) -> str:
        return (
            "Evaluate the agent step.\n"
            f"Step: {step_result.step_id}\n"
            f"Success: {step_result.success}\n"
            f"Error: {step_result.error}\n"
            f"Output: {step_result.output}"
        )
