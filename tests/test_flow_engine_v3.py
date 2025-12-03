import asyncio

from namel3ss.agent.engine import AgentRunner
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.flows.engine import FlowEngine
from namel3ss.flows.graph import FlowGraph, FlowNode, FlowRuntimeContext, FlowState
from namel3ss.ir import IRAgent, IRAiCall, IRFlow, IRFlowStep, IRModel, IRProgram
from namel3ss.metrics.tracker import MetricsTracker
from namel3ss.runtime.context import ExecutionContext
from namel3ss.tools.registry import ToolRegistry
from namel3ss.obs.tracer import Tracer


def build_engine(metrics: MetricsTracker | None = None) -> tuple[FlowEngine, FlowRuntimeContext]:
    program = IRProgram(
        ai_calls={"ask": IRAiCall(name="ask", model_name="default")},
        agents={"helper": IRAgent(name="helper")},
        models={"default": IRModel(name="default")},
    )
    model_registry = ModelRegistry()
    model_registry.register_model("default", provider_name=None)
    tool_registry = ToolRegistry()
    router = ModelRouter(model_registry)
    agent_runner = AgentRunner(program, model_registry, tool_registry, router)
    tracker = metrics or MetricsTracker()
    engine = FlowEngine(
        program=program,
        model_registry=model_registry,
        tool_registry=tool_registry,
        agent_runner=agent_runner,
        router=router,
        metrics=tracker,
    )
    exec_ctx = ExecutionContext(
        app_name="test",
        request_id="req-flow",
        tracer=None,
        tool_registry=tool_registry,
        metrics=tracker,
    )
    runtime_ctx = FlowRuntimeContext(
        program=program,
        model_registry=model_registry,
        tool_registry=tool_registry,
        agent_runner=agent_runner,
        router=router,
        tracer=None,
        metrics=tracker,
        secrets=None,
        memory_engine=None,
        rag_engine=None,
        execution_context=exec_ctx,
        max_parallel_tasks=4,
        parallel_semaphore=asyncio.Semaphore(4),
    )
    return engine, runtime_ctx


def test_branching_uses_shared_state():
    engine, runtime_ctx = build_engine()
    graph = FlowGraph(
        nodes={
            "start": FlowNode(
                id="start", kind="noop", config={"step_name": "start", "output": {"value": 5}}, next_ids=["branch"]
            ),
            "branch": FlowNode(
                id="branch",
                kind="branch",
                config={
                    "step_name": "branch",
                    "condition": "state.get('step.start.output')['value'] > 0",
                    "branches": {"true": "positive", "false": "negative"},
                },
                next_ids=[],
            ),
            "positive": FlowNode(
                id="positive",
                kind="noop",
                config={"step_name": "positive", "output": "ok"},
                next_ids=[],
            ),
            "negative": FlowNode(
                id="negative",
                kind="noop",
                config={"step_name": "negative", "output": "bad"},
                next_ids=[],
            ),
        },
        entry_id="start",
    )
    result = asyncio.run(engine.a_run_flow(graph, FlowState(), runtime_ctx, flow_name="branching"))
    assert result.state is not None
    assert result.state.get("step.positive.output") == "ok"
    assert result.errors == []


def test_parallel_join_merges_state_and_records_metrics():
    metrics = MetricsTracker()
    engine, runtime_ctx = build_engine(metrics=metrics)
    graph = FlowGraph(
        nodes={
            "start": FlowNode(id="start", kind="noop", config={"step_name": "start"}, next_ids=["fanout"]),
            "fanout": FlowNode(
                id="fanout", kind="noop", config={"step_name": "fanout", "join": "join"}, next_ids=["a", "b"]
            ),
            "a": FlowNode(id="a", kind="noop", config={"step_name": "a", "output": "A"}, next_ids=["join"]),
            "b": FlowNode(id="b", kind="noop", config={"step_name": "b", "output": "B"}, next_ids=["join"]),
            "join": FlowNode(id="join", kind="join", config={"step_name": "join"}, next_ids=["after"]),
            "after": FlowNode(id="after", kind="noop", config={"step_name": "after", "output": "done"}, next_ids=[]),
        },
        entry_id="start",
    )
    result = asyncio.run(engine.a_run_flow(graph, FlowState(), runtime_ctx, flow_name="parallel"))
    assert result.state.get("step.a.output") == "A"
    assert result.state.get("step.b.output") == "B"
    assert result.state.get("step.join.output") == {"join": True}
    assert metrics.snapshot()["flow_metrics"]["parallel_branches"] == 2


def test_error_boundary_handles_and_continues():
    engine, runtime_ctx = build_engine()

    def boom(_state):
        raise ValueError("boom")

    graph = FlowGraph(
        nodes={
            "fail": FlowNode(
                id="fail",
                kind="function",
                config={"step_name": "fail", "callable": boom},
                next_ids=[],
                error_boundary_id="handler",
            ),
            "handler": FlowNode(
                id="handler",
                kind="noop",
                config={"step_name": "handler", "output": "recovered"},
                next_ids=[],
            ),
        },
        entry_id="fail",
    )
    result = asyncio.run(engine.a_run_flow(graph, FlowState(), runtime_ctx, flow_name="errors"))
    assert any(err.handled for err in result.errors)
    assert result.state.get("step.handler.output") == "recovered"


def test_unhandled_error_surfaces():
    engine, runtime_ctx = build_engine()

    def boom(_state):
        raise RuntimeError("unhandled")

    graph = FlowGraph(
        nodes={
            "fail": FlowNode(
                id="fail",
                kind="function",
                config={"step_name": "fail", "callable": boom},
                next_ids=[],
            )
        },
        entry_id="fail",
    )
    result = asyncio.run(engine.a_run_flow(graph, FlowState(), runtime_ctx, flow_name="errors"))
    assert result.errors
    assert result.steps[-1].success is False


def test_tracer_records_flow_events():
    engine, runtime_ctx = build_engine()
    tracer = Tracer()
    runtime_ctx.tracer = tracer
    runtime_ctx.execution_context.tracer = tracer
    tracer.start_app("demo")
    tracer.start_flow("flow_trace")
    graph = FlowGraph(
        nodes={
            "fanout": FlowNode(
                id="fanout", kind="noop", config={"step_name": "fanout", "join": "join"}, next_ids=["left", "right"]
            ),
            "left": FlowNode(id="left", kind="noop", config={"step_name": "left"}, next_ids=["join"]),
            "right": FlowNode(
                id="right",
                kind="branch",
                config={
                    "step_name": "right",
                    "condition": "state.get('step.left.output') is None",
                    "branches": {"true": "join", "false": "join"},
                },
                next_ids=["join"],
            ),
            "join": FlowNode(id="join", kind="join", config={"step_name": "join"}, next_ids=[]),
        },
        entry_id="fanout",
    )
    asyncio.run(engine.a_run_flow(graph, FlowState(), runtime_ctx, flow_name="flow_trace"))
    events = tracer.last_trace.flows[0].events
    assert any(evt["event"] == "flow.parallel.start" for evt in events)
    assert any(evt["event"] == "flow.branch.eval" for evt in events)


def test_state_passing_between_steps():
    program = IRProgram(
        flows={
            "pipeline": IRFlow(
                name="pipeline",
                description=None,
                steps=[
                    IRFlowStep(name="first", kind="ai", target="ask"),
                    IRFlowStep(name="second", kind="agent", target="helper"),
                ],
            )
        },
        ai_calls={"ask": IRAiCall(name="ask", model_name="default")},
        agents={"helper": IRAgent(name="helper")},
        models={"default": IRModel(name="default")},
    )
    model_registry = ModelRegistry()
    model_registry.register_model("default", provider_name=None)
    tool_registry = ToolRegistry()
    router = ModelRouter(model_registry)
    engine = FlowEngine(
        program=program,
        model_registry=model_registry,
        tool_registry=tool_registry,
        agent_runner=AgentRunner(program, model_registry, tool_registry, router),
        router=router,
    )
    context = ExecutionContext(app_name="demo", request_id="req-1")
    result = engine.run_flow(program.flows["pipeline"], context)
    assert result.flow_name == "pipeline"
    assert result.state is not None
    assert "step.first.output" in result.state.data
