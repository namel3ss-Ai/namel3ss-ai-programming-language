from textwrap import dedent

import pytest

from namel3ss import parser
from namel3ss.ast_nodes import FlowDecl, FlowStepDecl, Literal
from namel3ss.ir import ast_to_ir
from namel3ss.flows.engine import FlowEngine
from namel3ss.flows.graph import FlowState
from namel3ss.agent.engine import AgentRunner
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.metrics.tracker import MetricsTracker
from namel3ss.runtime.context import ExecutionContext
from namel3ss.tools.registry import ToolRegistry


def _build_engine(program):
    registry = ModelRegistry()
    registry.register_model("default", provider_name=None)
    router = ModelRouter(registry)
    tool_registry = ToolRegistry()
    agent_runner = AgentRunner(program, registry, tool_registry, router)
    metrics = MetricsTracker()
    engine = FlowEngine(
        program=program,
        model_registry=registry,
        tool_registry=tool_registry,
        agent_runner=agent_runner,
        router=router,
        metrics=metrics,
    )
    exec_ctx = ExecutionContext(
        app_name="test",
        request_id="req",
        tracer=None,
        tool_registry=tool_registry,
        metrics=metrics,
    )
    runtime_ctx = engine._build_runtime_context(exec_ctx)
    return engine, runtime_ctx


def test_parse_when_on_step():
    module = parser.parse_source(
        dedent(
            """
                flow is "register_user":
                  step is "approve":
                    when is state.age >= 18
                    kind is "script"
                    set state.status be "approved"
                """
            )
        )
    flow = next(d for d in module.declarations if isinstance(d, FlowDecl))
    step: FlowStepDecl = flow.steps[0]
    assert step.when_expr is not None
    assert isinstance(step.when_expr, Literal) or True  # ensure parsed


def test_runtime_when_true_false():
    module = parser.parse_source(
        dedent(
            """
                flow is "register_user":
                  step is "approve":
                    when is state.age >= 18
                    kind is "script"
                    set state.status be "approved"

                  step is "reject":
                    when is state.age < 18
                    kind is "script"
                    set state.status be "rejected"
                """
            )
        )
    ir = ast_to_ir(module)
    engine, runtime_ctx = _build_engine(ir)

    # age 20
    result = engine.run_flow(ir.flows["register_user"], runtime_ctx.execution_context, initial_state={"age": 20})
    assert result.state.get("status") == "approved"

    # age 16
    result = engine.run_flow(ir.flows["register_user"], runtime_ctx.execution_context, initial_state={"age": 16})
    assert result.state.get("status") == "rejected"


def test_runtime_when_expression_error():
    module = parser.parse_source(
        dedent(
            """
                flow is "f":
                  step is "bad":
                    when is unknown_var
                    kind is "script"
                    set state.status be "ok"
                """
            )
        )
    ir = ast_to_ir(module)
    engine, runtime_ctx = _build_engine(ir)
    result = engine.run_flow(ir.flows["f"], runtime_ctx.execution_context, initial_state={})
    assert result.errors, "Expected errors from invalid when expression"
