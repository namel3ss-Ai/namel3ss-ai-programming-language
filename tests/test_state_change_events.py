import asyncio

from namel3ss import ast_nodes
from namel3ss.agent.engine import AgentRunner
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.flows.engine import FlowEngine
from namel3ss.flows.models import StreamEvent
from namel3ss.ir import IRAgent, IRFlow, IRFlowStep, IRModel, IRProgram, IRSet
from namel3ss.metrics.tracker import MetricsTracker
from namel3ss.runtime.context import ExecutionContext
from namel3ss.tools.registry import ToolRegistry


def _build_engine() -> tuple[FlowEngine, ExecutionContext]:
    program = IRProgram(models={"default": IRModel(name="default")}, agents={"helper": IRAgent(name="helper")})
    registry = ModelRegistry()
    registry.register_model("default", provider_name=None)
    router = ModelRouter(registry)
    tools = ToolRegistry()
    agent_runner = AgentRunner(program, registry, tools, router)
    metrics = MetricsTracker()
    engine = FlowEngine(
        program=program,
        model_registry=registry,
        tool_registry=tools,
        agent_runner=agent_runner,
        router=router,
        metrics=metrics,
    )
    ctx = ExecutionContext(app_name="test", request_id="req", tracer=None, tool_registry=tools, metrics=metrics)
    return engine, ctx


def test_state_change_event_emitted_on_set():
    engine, ctx = _build_engine()
    events: list[StreamEvent] = []

    async def _callback(evt: StreamEvent):
        events.append(evt)

    flow = IRFlow(
        name="increment_counter",
        description=None,
        steps=[
            IRFlowStep(
                name="inc",
                kind="script",
                target="inc",
                statements=[
                    IRSet(
                        name="state.counter",
                        expr=ast_nodes.BinaryOp(
                            left=ast_nodes.Identifier(name="state.counter"),
                            op="+",
                            right=ast_nodes.Literal(value=1),
                        ),
                    )
                ],
            )
        ],
    )
    async def _run():
        return await engine.run_flow_async(flow, ctx, initial_state={"counter": 1}, stream_callback=_callback)

    result = asyncio.run(_run())
    assert result.state.get("counter") == 2
    state_events = [evt for evt in events if evt.get("kind") == "state_change"]
    assert state_events, "expected state_change event"
    evt = state_events[0]
    assert evt.get("path") == "counter"
    assert evt.get("old_value") == 1
    assert evt.get("new_value") == 2
