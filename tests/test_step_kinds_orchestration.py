from __future__ import annotations

import pytest

from namel3ss import ast_nodes
from namel3ss.agent.engine import AgentRunner
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.errors import Namel3ssError
from namel3ss.flows.engine import FlowEngine
from namel3ss.ir import (
    IRAgent,
    IRAiCall,
    IRAction,
    IRFlow,
    IRFlowLoop,
    IRFlowStep,
    IRForEach,
    IRLet,
    IRModel,
    IRProgram,
    IRRetry,
    IRSet,
)
from namel3ss.parser import parse_source
from namel3ss.ir import ast_to_ir
from namel3ss.runtime.context import ExecutionContext
from namel3ss.tools.registry import ToolConfig, ToolRegistry


class DummyAgentRunner:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def run(self, name: str, context: ExecutionContext):
        self.calls.append(name)
        return {"agent": name}


def _make_engine(
    flow: IRFlow,
    *,
    ai_calls: dict[str, IRAiCall] | None = None,
    agents: dict[str, IRAgent] | None = None,
    tools: list[ToolConfig] | None = None,
    program_override: IRProgram | None = None,
    agent_runner_override: AgentRunner | DummyAgentRunner | None = None,
):
    program = program_override or IRProgram(
        models={"default": IRModel(name="default")},
        ai_calls=ai_calls or {},
        agents=agents or {},
        flows={flow.name: flow},
    )
    registry = ModelRegistry()
    registry.register_model("default", provider_name=None)
    tool_registry = ToolRegistry()
    for tool in tools or []:
        tool_registry.register(tool)
    router = ModelRouter(registry)
    agent_runner = agent_runner_override or DummyAgentRunner()
    engine = FlowEngine(
        program=program,
        model_registry=registry,
        tool_registry=tool_registry,
        agent_runner=agent_runner,
        router=router,
        metrics=None,
        secrets=None,
    )
    ctx = ExecutionContext(
        app_name="test-app",
        request_id="req-step-kind",
        tracer=None,
        tool_registry=tool_registry,
        metrics=None,
    )
    return engine, ctx, agent_runner, tool_registry


def test_script_kind_runs_statements():
    flow = IRFlow(
        name="script_kind",
        description=None,
        steps=[
            IRFlowStep(
                name="compute",
                kind="script",
                target="script",
                statements=[
                    IRLet(name="x", expr=ast_nodes.Literal(value=1)),
                    IRSet(name="state.x", expr=ast_nodes.Identifier(name="x")),
                ],
            )
        ],
    )
    engine, ctx, _, _ = _make_engine(flow)
    result = engine.run_flow(flow, ctx)
    assert result.errors == []
    assert result.state.get("x") == 1


def test_script_kind_defaults_when_omitted():
    module = parse_source(
        'flow is "f":\n'
        '  step is "s":\n'
        '    let x be 2\n'
        '    set state.x be x\n'
    )
    ir_prog = ast_to_ir(module)
    flow = ir_prog.flows["f"]
    engine, ctx, _, _ = _make_engine(flow, program_override=ir_prog)
    result = engine.run_flow(flow, ctx)
    assert result.errors == []
    assert result.state.get("x") == 2


def test_ai_step_succeeds_and_sets_output():
    ai_calls = {"classifier": IRAiCall(name="classifier", model_name="default")}
    flow = IRFlow(
        name="ai_flow",
        description=None,
        steps=[IRFlowStep(name="call", kind="ai", target="classifier", statements=None, params={}, message=None)],
    )
    engine, ctx, _, _ = _make_engine(flow, ai_calls=ai_calls)

    async def fake_call(**kwargs):
        return {"label": "ok"}

    engine._call_ai_step = fake_call  # type: ignore[attr-defined]
    result = engine.run_flow(flow, ctx)
    assert result.errors == []
    assert result.state.get("step.call.output") == {"label": "ok"}
    assert result.state.get("last_output") == {"label": "ok"}


def test_ai_step_missing_target_errors():
    ai_calls = {"classifier": IRAiCall(name="classifier", model_name="default")}
    flow = IRFlow(
        name="ai_missing_target",
        description=None,
        steps=[IRFlowStep(name="call", kind="ai", target="", statements=None, params={}, message=None)],
    )
    engine, ctx, _, _ = _make_engine(flow, ai_calls=ai_calls)
    result = engine.run_flow(flow, ctx)
    assert result.errors
    assert result.errors[0].error == "This AI step needs a target (the model to call), but none was provided."


def test_ai_step_unknown_target_errors():
    flow = IRFlow(
        name="ai_unknown_target",
        description=None,
        steps=[IRFlowStep(name="call", kind="ai", target="missing", statements=None, params={}, message=None)],
    )
    engine, ctx, _, _ = _make_engine(flow)
    result = engine.run_flow(flow, ctx)
    assert result.errors
    assert result.errors[0].error == 'I couldn\'t find an AI call named "missing". Check your configuration or plugin setup.'


def test_agent_step_runs_runner():
    agents = {"support": IRAgent(name="support")}
    flow = IRFlow(
        name="agent_flow",
        description=None,
        steps=[IRFlowStep(name="delegate", kind="agent", target="support", statements=None, params={}, message=None)],
    )
    engine, ctx, agent_runner, _ = _make_engine(flow, agents=agents)
    result = engine.run_flow(flow, ctx)
    assert result.errors == []
    assert agent_runner.calls == ["support"]
    assert result.state.get("step.delegate.output") == {"agent": "support"}


def test_agent_step_missing_or_unknown_target_errors():
    agents = {"support": IRAgent(name="support")}
    missing_flow = IRFlow(
        name="agent_missing",
        description=None,
        steps=[IRFlowStep(name="delegate", kind="agent", target="", statements=None, params={}, message=None)],
    )
    engine, ctx, _, _ = _make_engine(missing_flow, agents=agents)
    result = engine.run_flow(missing_flow, ctx)
    assert result.errors
    assert result.errors[0].error == "This agent step needs a target (the agent to run), but none was provided."

    unknown_flow = IRFlow(
        name="agent_unknown",
        description=None,
        steps=[IRFlowStep(name="delegate", kind="agent", target="ghost", statements=None, params={}, message=None)],
    )
    engine2, ctx2, _, _ = _make_engine(unknown_flow, agents=agents)
    result2 = engine2.run_flow(unknown_flow, ctx2)
    assert result2.errors
    assert result2.errors[0].error == 'I couldn\'t find an agent named "ghost". Check your configuration or plugin setup.'


def test_tool_step_uses_last_output_as_default_payload():
    class RecordingTool:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def execute(self, args: dict) -> dict:
            self.calls.append(args)
            return {"ok": args}

    recorder = RecordingTool()
    tool_cfg = ToolConfig(name="echo", kind="custom", method="POST")
    tool_cfg.execute = recorder.execute  # type: ignore[attr-defined]

    flow = IRFlow(
        name="tool_flow",
        description=None,
        steps=[
            IRFlowStep(
                name="prep",
                kind="script",
                target="script",
                statements=[
                    IRLet(name="value", expr=ast_nodes.Literal(value=5)),
                    IRSet(name="state.value", expr=ast_nodes.Identifier(name="value")),
                ],
            ),
            IRFlowStep(name="call", kind="tool", target="echo", statements=None, params={}, message=None),
        ],
    )
    engine, ctx, _, tools = _make_engine(flow, tools=[tool_cfg])
    result = engine.run_flow(flow, ctx)
    assert result.errors == []
    assert recorder.calls == [{"message": 5}]
    assert result.state.get("step.call.output") == {"ok": {"message": 5}}


def test_tool_missing_or_unknown_target_errors():
    flow_missing = IRFlow(
        name="tool_missing",
        description=None,
        steps=[IRFlowStep(name="call", kind="tool", target="", statements=None, params={}, message=None)],
    )
    engine, ctx, _, _ = _make_engine(flow_missing)
    result = engine.run_flow(flow_missing, ctx)
    assert result.errors
    assert result.errors[0].error == "This tool step needs a target (the tool name), but none was provided."

    flow_unknown = IRFlow(
        name="tool_unknown",
        description=None,
        steps=[IRFlowStep(name="call", kind="tool", target="ghost", statements=None, params={}, message=None)],
    )
    engine2, ctx2, _, _ = _make_engine(flow_unknown)
    result2 = engine2.run_flow(flow_unknown, ctx2)
    assert result2.errors
    assert result2.errors[0].error == 'I couldn\'t find a tool named "ghost". Check your configuration or plugin setup.'


def test_retry_wraps_ai_step():
    attempts: list[int] = []

    async def flaky_call(**kwargs):
        attempts.append(len(attempts))
        if len(attempts) == 1:
            return {"error": "fail"}
        return {"ok": True}

    ai_calls = {"classifier": IRAiCall(name="classifier", model_name="default")}
    flow = IRFlow(
        name="retry_ai",
        description=None,
        steps=[
            IRFlowStep(
                name="script",
                kind="script",
                target="script",
                statements=[
                    IRRetry(
                        count=ast_nodes.Literal(value=2),
                        with_backoff=False,
                        body=[IRAction(kind="ai", target="classifier", message=None, args={})],
                    )
                ],
            )
        ],
    )
    engine, ctx, _, _ = _make_engine(flow, ai_calls=ai_calls)
    engine._call_ai_step = flaky_call  # type: ignore[attr-defined]
    result = engine.run_flow(flow, ctx)
    assert result.errors == []
    assert attempts == [0, 1]
    assert result.state.get("last_output") == {"ok": True}


def test_on_error_catches_tool_failure():
    class FailingTool:
        def execute(self, args: dict):
            raise Namel3ssError("boom")

    tool_cfg = ToolConfig(name="boom", kind="custom", method="POST")
    tool_cfg.execute = FailingTool().execute  # type: ignore[attr-defined]
    flow = IRFlow(
        name="tool_error",
        description=None,
        steps=[IRFlowStep(name="call", kind="tool", target="boom", statements=None, params={}, message=None)],
        error_steps=[IRFlowStep(name="handler", kind="script", target="script", statements=[IRSet(name="state.handled", expr=ast_nodes.Literal(value=True))])],
    )
    engine, ctx, _, _ = _make_engine(flow, tools=[tool_cfg])
    result = engine.run_flow(flow, ctx)
    assert result.errors == []
    assert result.state.get("handled") is True


def test_flow_loop_calls_tool_each_iteration():
    class RecordingTool:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def execute(self, args: dict) -> dict:
            self.calls.append(args)
            return {"ok": args}

    recorder = RecordingTool()
    tool_cfg = ToolConfig(name="loop_tool", kind="custom", method="POST")
    tool_cfg.execute = recorder.execute  # type: ignore[attr-defined]

    loop = IRFlowLoop(
        name="loop",
        var_name="item",
        iterable=ast_nodes.Identifier(name="state.items"),
        body=[
            IRFlowStep(
                name="call",
                kind="tool",
                target="loop_tool",
                params={"input": {"message": ast_nodes.Identifier(name="item")}},
                statements=None,
                message=None,
            )
        ],
    )
    flow = IRFlow(
        name="flow_loop",
        description=None,
        steps=[
            IRFlowStep(
                name="init",
                kind="script",
                target="script",
                statements=[IRSet(name="state.items", expr=ast_nodes.ListLiteral(items=[ast_nodes.Literal(value=1), ast_nodes.Literal(value=2)]))],
            ),
            loop,
        ],
    )
    engine, ctx, _, _ = _make_engine(flow, tools=[tool_cfg])
    result = engine.run_flow(flow, ctx)
    assert result.errors == []
    assert recorder.calls == [{"message": 1}, {"message": 2}]
