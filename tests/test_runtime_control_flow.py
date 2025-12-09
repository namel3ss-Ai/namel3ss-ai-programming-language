from __future__ import annotations

from namel3ss import ast_nodes
from namel3ss.agent.engine import AgentRunner
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.flows.engine import FlowEngine
from namel3ss.ir import (
    IRAgent,
    IRConditionalBranch,
    IRFlow,
    IRFlowStep,
    IRIf,
    IRMatch,
    IRMatchBranch,
    IRModel,
    IRProgram,
    IRSet,
)
from namel3ss.runtime.context import ExecutionContext
from namel3ss.tools.registry import ToolRegistry


def _script_step(name: str, statements: list) -> IRFlowStep:
    return IRFlowStep(name=name, kind="script", target="script", statements=statements)


def _build_engine(flow: IRFlow) -> tuple[FlowEngine, ExecutionContext]:
    program = IRProgram(
        models={"default": IRModel(name="default")},
        agents={"helper": IRAgent(name="helper")},
        flows={flow.name: flow},
    )
    registry = ModelRegistry()
    registry.register_model("default", provider_name=None)
    tool_registry = ToolRegistry()
    router = ModelRouter(registry)
    agent_runner = AgentRunner(program, registry, tool_registry, router)
    engine = FlowEngine(
        program=program,
        model_registry=registry,
        tool_registry=tool_registry,
        agent_runner=agent_runner,
        router=router,
    )
    context = ExecutionContext(
        app_name="test-app",
        request_id="req-1",
        tracer=None,
        tool_registry=tool_registry,
        metrics=None,
    )
    return engine, context


def _run_flow(flow: IRFlow, initial_state: dict | None = None):
    engine, context = _build_engine(flow)
    return engine.run_flow(flow, context, initial_state=initial_state or {})


def test_if_only_first_true_branch_runs():
    flow = IRFlow(
        name="first_true",
        description=None,
        steps=[
            _script_step(
                "script",
                [
                    IRIf(
                        branches=[
                            IRConditionalBranch(
                                condition=ast_nodes.Literal(value=True),
                                actions=[IRSet(name="state.selection", expr=ast_nodes.Literal(value="first"))],
                            ),
                            IRConditionalBranch(
                                condition=ast_nodes.Literal(value=True),
                                actions=[IRSet(name="state.selection", expr=ast_nodes.Literal(value="second"))],
                            ),
                        ]
                    )
                ],
            )
        ],
    )
    result = _run_flow(flow)
    assert result.state.get("selection") == "first"


def test_if_else_runs_when_all_conditions_fail():
    flow = IRFlow(
        name="else_path",
        description=None,
        steps=[
            _script_step(
                "script",
                [
                    IRIf(
                        branches=[
                            IRConditionalBranch(
                                condition=ast_nodes.Literal(value=False),
                                actions=[IRSet(name="state.outcome", expr=ast_nodes.Literal(value="skip"))],
                            ),
                            IRConditionalBranch(
                                condition=None,
                                actions=[IRSet(name="state.outcome", expr=ast_nodes.Literal(value="fallback"))],
                                label="else",
                            ),
                        ]
                    )
                ],
            )
        ],
    )
    result = _run_flow(flow)
    assert result.state.get("outcome") == "fallback"


def test_if_condition_must_be_boolean():
    flow = IRFlow(
        name="invalid_if",
        description=None,
        steps=[
            _script_step(
                "script",
                [
                    IRIf(
                        branches=[
                            IRConditionalBranch(
                                condition=ast_nodes.Literal(value="sure"),
                                actions=[IRSet(name="state.flag", expr=ast_nodes.Literal(value=True))],
                            )
                        ]
                    )
                ],
            )
        ],
    )
    result = _run_flow(flow)
    assert result.errors, "expected the flow to record the condition failure"
    assert (
        result.errors[0].error
        == "This if condition did not evaluate to a boolean value.\nI got 'sure' instead. Make sure the condition returns true or false."
    )


def test_match_selects_branch_by_literal_value():
    flow = IRFlow(
        name="match_literals",
        description=None,
        steps=[
            _script_step(
                "router",
                [
                    IRMatch(
                        target=ast_nodes.Identifier(name="state.intent"),
                        branches=[
                            IRMatchBranch(
                                pattern=ast_nodes.Literal(value="billing"),
                                actions=[IRSet(name="state.route", expr=ast_nodes.Literal(value="billing_flow"))],
                            ),
                            IRMatchBranch(
                                pattern=ast_nodes.Literal(value="support"),
                                actions=[IRSet(name="state.route", expr=ast_nodes.Literal(value="support_flow"))],
                            ),
                            IRMatchBranch(
                                pattern=None,
                                actions=[IRSet(name="state.route", expr=ast_nodes.Literal(value="fallback_flow"))],
                                label="otherwise",
                            ),
                        ],
                    )
                ],
            )
        ],
    )
    result = _run_flow(flow, initial_state={"intent": "support"})
    assert result.state.get("route") == "support_flow"


def test_match_uses_otherwise_when_nothing_matches():
    flow = IRFlow(
        name="match_fallback",
        description=None,
        steps=[
            _script_step(
                "router",
                [
                    IRMatch(
                        target=ast_nodes.Identifier(name="state.intent"),
                        branches=[
                            IRMatchBranch(
                                pattern=ast_nodes.Literal(value="billing"),
                                actions=[IRSet(name="state.route", expr=ast_nodes.Literal(value="billing_flow"))],
                            ),
                            IRMatchBranch(
                                pattern=None,
                                actions=[IRSet(name="state.route", expr=ast_nodes.Literal(value="fallback_flow"))],
                                label="otherwise",
                            ),
                        ],
                    )
                ],
            )
        ],
    )
    result = _run_flow(flow, initial_state={"intent": "unknown"})
    assert result.state.get("route") == "fallback_flow"


def test_match_without_otherwise_is_noop_when_no_branch_hits():
    flow = IRFlow(
        name="match_noop",
        description=None,
        steps=[
            _script_step(
                "router",
                [
                    IRMatch(
                        target=ast_nodes.Identifier(name="state.intent"),
                        branches=[
                            IRMatchBranch(
                                pattern=ast_nodes.Literal(value="alpha"),
                                actions=[IRSet(name="state.route", expr=ast_nodes.Literal(value="alpha_flow"))],
                            ),
                            IRMatchBranch(
                                pattern=ast_nodes.Literal(value="beta"),
                                actions=[IRSet(name="state.route", expr=ast_nodes.Literal(value="beta_flow"))],
                            ),
                        ],
                    )
                ],
            )
        ],
    )
    result = _run_flow(flow, initial_state={"intent": "gamma"})
    assert "route" not in result.state.data


def test_match_boolean_branch_only_triggers_on_true():
    flow = IRFlow(
        name="match_bool",
        description=None,
        steps=[
            _script_step(
                "router",
                [
                    IRMatch(
                        target=ast_nodes.Identifier(name="state.flag"),
                        branches=[
                            IRMatchBranch(
                                pattern=ast_nodes.Literal(value=True),
                                actions=[IRSet(name="state.result", expr=ast_nodes.Literal(value="true-branch"))],
                            ),
                            IRMatchBranch(
                                pattern=None,
                                actions=[IRSet(name="state.result", expr=ast_nodes.Literal(value="fallback"))],
                                label="otherwise",
                            ),
                        ],
                    )
                ],
            )
        ],
    )
    true_result = _run_flow(flow, initial_state={"flag": True})
    false_result = _run_flow(flow, initial_state={"flag": False})
    assert true_result.state.get("result") == "true-branch"
    assert false_result.state.get("result") == "fallback"


def test_on_error_handler_runs_on_failure():
    failing_step = _script_step(
        "primary",
        [
            IRIf(
                branches=[
                    IRConditionalBranch(
                        condition=ast_nodes.Identifier(name="missing_variable"),
                        actions=[IRSet(name="state.unreachable", expr=ast_nodes.Literal(value=True))],
                    )
                ]
            )
        ],
    )
    handler_step = _script_step(
        "on_error_handler",
        [IRSet(name="state.recovered", expr=ast_nodes.Literal(value=True))],
    )
    flow = IRFlow(
        name="with_error_handler",
        description=None,
        steps=[failing_step],
        error_steps=[handler_step],
    )
    result = _run_flow(flow)
    assert result.errors == []
    assert result.state.get("recovered") is True


def test_on_error_handler_not_triggered_when_step_succeeds():
    primary_step = _script_step(
        "primary",
        [IRSet(name="state.primary", expr=ast_nodes.Literal(value="ok"))],
    )
    handler_step = _script_step(
        "on_error_handler",
        [IRSet(name="state.recovered", expr=ast_nodes.Literal(value=True))],
    )
    flow = IRFlow(
        name="handler_not_needed",
        description=None,
        steps=[primary_step],
        error_steps=[handler_step],
    )
    result = _run_flow(flow)
    assert result.errors == []
    assert result.state.get("primary") == "ok"
    assert result.state.get("recovered") is None


def test_flow_without_on_error_propagates_failure():
    failing_step = _script_step(
        "primary",
        [
            IRIf(
                branches=[
                    IRConditionalBranch(
                        condition=ast_nodes.Identifier(name="missing_variable"),
                        actions=[IRSet(name="state.unreachable", expr=ast_nodes.Literal(value=True))],
                    )
                ]
            )
        ],
    )
    flow = IRFlow(
        name="no_handler",
        description=None,
        steps=[failing_step],
    )
    result = _run_flow(flow)
    assert result.errors
    assert "missing_variable" in result.errors[0].error
