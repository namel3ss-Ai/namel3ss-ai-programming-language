"""
Flow execution engine.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Optional

from ..agent.engine import AgentRunner
from ..ai.registry import ModelRegistry
from ..errors import Namel3ssError
from ..ir import IRFlow, IRProgram
from ..runtime.context import ExecutionContext, execute_ai_call_with_registry
from ..tools.registry import ToolRegistry
from .models import FlowRunResult, FlowStepResult


class FlowEngine:
    def __init__(
        self,
        program: IRProgram,
        model_registry: ModelRegistry,
        tool_registry: ToolRegistry,
        agent_runner: AgentRunner,
        router,
    ) -> None:
        self.program = program
        self.model_registry = model_registry
        self.tool_registry = tool_registry
        self.agent_runner = agent_runner
        self.router = router

    def run_flow(
        self, flow: IRFlow, context: ExecutionContext
    ) -> FlowRunResult:
        if context.tracer:
            context.tracer.start_flow(flow.name)

        results: list[FlowStepResult] = []
        for step in flow.steps:
            try:
                output = self._execute_step(step.kind, step.target, context)
                results.append(
                    FlowStepResult(
                        step_name=step.name,
                        kind=step.kind,
                        target=step.target,
                        success=True,
                        output=output,
                    )
                )
                if context.tracer:
                    context.tracer.record_flow_step(
                        step_name=step.name,
                        kind=step.kind,
                        target=step.target,
                        success=True,
                        output_preview=str(output)[:200] if output is not None else None,
                    )
            except Exception as exc:
                results.append(
                    FlowStepResult(
                        step_name=step.name,
                        kind=step.kind,
                        target=step.target,
                        success=False,
                        error_message=str(exc),
                    )
                )
                if context.tracer:
                    context.tracer.record_flow_step(
                        step_name=step.name,
                        kind=step.kind,
                        target=step.target,
                        success=False,
                        output_preview=str(exc),
                    )
                break
        if context.tracer:
            context.tracer.end_flow()
        return FlowRunResult(flow_name=flow.name, steps=results)

    def _execute_step(self, kind: str, target: str, context: ExecutionContext):
        if kind == "ai":
            if target not in self.program.ai_calls:
                raise Namel3ssError(f"Flow AI target '{target}' not found")
            ai_call = self.program.ai_calls[target]
            return execute_ai_call_with_registry(
                ai_call, self.model_registry, self.router, context
            )
        if kind == "agent":
            return asdict(self.agent_runner.run(target, context))
        if kind == "tool":
            tool = self.tool_registry.get(target)
            if not tool:
                raise Namel3ssError(f"Flow tool target '{target}' not found")
            return tool.run(message="flow", a=1, b=1)
        raise Namel3ssError(f"Unsupported flow step kind '{kind}'")
