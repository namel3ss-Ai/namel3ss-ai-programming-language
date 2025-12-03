"""
Agent execution engine with reflection, planning, and retries.
"""

from __future__ import annotations

from typing import Optional

from ..ai.registry import ModelRegistry
from ..errors import Namel3ssError
from ..ir import IRAgent, IRProgram
from ..runtime.context import ExecutionContext, execute_ai_call_with_registry
from ..tools.registry import ToolRegistry
from .evaluators import AgentStepEvaluator, DeterministicEvaluator, OpenAIEvaluator
from .plan import AgentExecutionPlan, AgentPlanResult, AgentStep, AgentStepResult


class AgentRunner:
    def __init__(
        self,
        program: IRProgram,
        model_registry: ModelRegistry,
        tool_registry: ToolRegistry,
        router,
        evaluator: Optional[AgentStepEvaluator] = None,
    ) -> None:
        self.program = program
        self.model_registry = model_registry
        self.tool_registry = tool_registry
        self.router = router
        self.evaluator = evaluator or DeterministicEvaluator(max_retries=1)

    def build_plan(self, agent: IRAgent, page_ai_fallback: Optional[str] = None) -> AgentExecutionPlan:
        steps: list[AgentStep] = []
        target_ai = page_ai_fallback or next(iter(self.program.ai_calls), None)
        if target_ai:
            steps.append(
                AgentStep(
                    id="call_model",
                    kind="ai",
                    target=target_ai,
                    description="Invoke AI call",
                    max_retries=1,
                )
            )
        if "echo" in self.tool_registry.list_names():
            steps.append(
                AgentStep(
                    id="echo_result",
                    kind="tool",
                    target="echo",
                    description="Echo last output",
                )
            )
        return AgentExecutionPlan(steps=steps, current_index=0, max_retries_per_step=1)

    def run(
        self,
        agent_name: str,
        context: ExecutionContext,
        page_ai_fallback: Optional[str] = None,
    ) -> AgentPlanResult:
        if agent_name not in self.program.agents:
            raise Namel3ssError(f"Unknown agent '{agent_name}'")
        agent = self.program.agents[agent_name]
        plan = self.build_plan(agent, page_ai_fallback=page_ai_fallback)
        results: list[AgentStepResult] = []

        if context.tracer:
            context.tracer.start_agent(agent.name)

        # Allow OpenAI-backed evaluator when secrets configured.
        if isinstance(self.evaluator, DeterministicEvaluator) and context.secrets:
            if context.secrets.get("N3_OPENAI_API_KEY"):
                self.evaluator = OpenAIEvaluator(
                    registry=self.model_registry,
                    router=self.router,
                    secrets=context.secrets,
                )

        last_output: Optional[dict] = None
        stopped = False
        while True:
            step = plan.next_step()
            if not step or stopped:
                break
            attempt = 0
            success = False
            output = None
            error: Optional[str] = None
            last_result: Optional[AgentStepResult] = None
            while attempt <= max(step.max_retries, plan.max_retries_per_step) and not stopped:
                try:
                    output = self._run_step(step, last_output, context)
                    success = True
                except Exception as exc:  # pragma: no cover - retry path
                    error = str(exc)
                    success = False
                result = AgentStepResult(
                    step_id=step.id,
                    input={"previous": last_output},
                    output=output if isinstance(output, dict) else {"value": output},
                    success=success,
                    error=error,
                    retries=attempt,
                )
                evaluation = self.evaluator.evaluate(result, context)
                result.evaluation = evaluation
                last_result = result
                if context.metrics:
                    context.metrics.record_evaluation()
                if context.tracer:
                    context.tracer.record_agent_step(
                        step_name=step.id,
                        kind=step.kind,
                        target=step.target,
                        success=success,
                        retries=attempt,
                        output_preview=str(output)[:200] if output is not None else None,
                        evaluation_score=evaluation.score,
                        verdict=evaluation.verdict,
                    )
                if context.tracer:
                    pass
                if evaluation.verdict == "accept":
                    break
                if evaluation.verdict == "retry" and attempt < max(step.max_retries, plan.max_retries_per_step):
                    attempt += 1
                    if context.metrics:
                        context.metrics.record_retry()
                    continue
                if evaluation.verdict in {"stop", "escalate"}:
                    stopped = True
                break
            if last_result:
                results.append(last_result)
            last_output = output
            if stopped:
                break

        summary = f"Agent {agent.name} finished {len(results)} steps."
        if stopped:
            summary = f"Agent {agent.name} halted after {len(results)} steps."
        if context.tracer:
            context.tracer.end_agent(summary=summary)
        if context.metrics:
            context.metrics.record_agent_run()
        return AgentPlanResult(agent_name=agent.name, steps=results, summary=summary)

    def _run_step(self, step: AgentStep, last_output: Optional[dict], context: ExecutionContext):
        if step.kind == "tool":
            tool = self.tool_registry.get(step.target)
            if not tool:
                raise Namel3ssError(f"Tool '{step.target}' not found")
            result = tool.run(message=str(last_output) if last_output else "", **step.config)
            if context.metrics:
                context.metrics.record_tool_call(provider=step.target, cost=0.0005)
            return result
        if step.kind == "ai":
            if step.target not in self.program.ai_calls:
                raise Namel3ssError(f"AI call '{step.target}' not found")
            ai_call = self.program.ai_calls[step.target]
            return execute_ai_call_with_registry(ai_call, self.model_registry, self.router, context)
        if step.kind == "subagent":
            if step.target not in self.program.agents:
                raise Namel3ssError(f"Sub-agent '{step.target}' not found")
            return {"subagent": step.target}
        raise Namel3ssError(f"Unsupported step kind '{step.kind}'")
