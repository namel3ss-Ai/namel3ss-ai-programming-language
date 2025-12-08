from textwrap import dedent
import asyncio

import pytest

from namel3ss import parser
from namel3ss.ast_nodes import FlowDecl
from namel3ss.flows.engine import FlowEngine
from namel3ss.flows.graph import FlowGraph, FlowNode, FlowRuntimeContext, FlowState
from namel3ss.ir import IRFlow, IRFlowStep, IRProgram
from namel3ss.runtime.context import ExecutionContext
from namel3ss.agent.engine import AgentRunner
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.tools.registry import ToolRegistry


def test_parse_flow_with_error_handler():
    module = parser.parse_source(
        dedent(
            """
            flow is "answer_user":
              step is "call_ai":
                kind is "ai"
                target is "support_bot"

              on error:
                step is "fallback":
                  kind is "tool"
                  tool is "noop"
            """
        )
    )
    flows = [decl for decl in module.declarations if isinstance(decl, FlowDecl)]
    assert len(flows) == 1
    flow = flows[0]
    assert len(flow.steps) == 1
    assert len(flow.error_steps) == 1


def test_parse_multiple_on_error_raises():
    with pytest.raises(Exception):
        parser.parse_source(
            dedent(
                """
                flow is "bad":
                  step is "one":
                    kind is "ai"
                    target is "missing"

                  on error:
                    step is "fallback":
                      kind is "tool"
                      tool is "noop"

                  on error:
                    step is "fallback2":
                      kind is "tool"
                      tool is "noop"
                """
            )
        )


def build_runtime():
    program = IRProgram(ai_calls={}, agents={}, models={})
    model_registry = ModelRegistry()
    router = ModelRouter(model_registry)
    tool_registry = ToolRegistry()
    agent_runner = AgentRunner(program, model_registry, tool_registry, router)
    exec_ctx = ExecutionContext(app_name="test", request_id="req", tracer=None, tool_registry=tool_registry, metrics=None)
    runtime_ctx = FlowRuntimeContext(
        program=program,
        model_registry=model_registry,
        tool_registry=tool_registry,
        agent_runner=agent_runner,
        router=router,
        tracer=None,
        metrics=None,
        secrets=None,
        memory_engine=None,
        rag_engine=None,
        execution_context=exec_ctx,
        max_parallel_tasks=2,
        parallel_semaphore=None,
    )
    engine = FlowEngine(program, model_registry, tool_registry, agent_runner, router, metrics=None)
    return engine, runtime_ctx


def test_error_handler_runs_on_failure():
    engine, runtime_ctx = build_runtime()
    graph = FlowGraph(
        nodes={
            "fail": FlowNode(
                id="fail",
                kind="function",
                config={"step_name": "fail", "callable": lambda state: (_ for _ in ()).throw(Exception("boom"))},
                next_ids=[],
                error_boundary_id="error::handler",
            ),
            "error::handler": FlowNode(
                id="error::handler",
                kind="function",
                config={
                    "step_name": "handler",
                    "callable": lambda state: state.set("handled", True),
                },
                next_ids=[],
            ),
        },
        entry_id="fail",
    )
    result = asyncio.run(engine.a_run_flow(graph, FlowState(data={"handled": False}), runtime_ctx, flow_name="test"))
    assert result.errors == []
    assert result.state.get("handled") is True


def test_error_handler_not_triggered_on_success():
    engine, runtime_ctx = build_runtime()
    graph = FlowGraph(
        nodes={
            "ok": FlowNode(
                id="ok",
                kind="function",
                config={"step_name": "ok", "callable": lambda state: state.set("handled", False)},
                next_ids=[],
                error_boundary_id="error::handler",
            ),
            "error::handler": FlowNode(
                id="error::handler",
                kind="function",
                config={"step_name": "handler", "callable": lambda state: state.set("handled", True)},
                next_ids=[],
            ),
        },
        entry_id="ok",
    )
    result = asyncio.run(engine.a_run_flow(graph, FlowState(data={"handled": False}), runtime_ctx, flow_name="test"))
    assert result.errors == []
    assert result.state.get("handled") is False
