from namel3ss import ast_nodes
from namel3ss.ir import IRFrame, IRFlow, IRFlowStep, IRModel, IRAgent, IRProgram
from namel3ss.flows.engine import FlowEngine
from namel3ss.agent.engine import AgentRunner
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.tools.registry import ToolRegistry
from namel3ss.metrics.tracker import MetricsTracker
from namel3ss.runtime.context import ExecutionContext


def _engine(program: IRProgram):
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
    ctx = ExecutionContext(app_name="app", request_id="req-log", tracer=None, tool_registry=tool_registry, metrics=metrics)
    return engine, ctx


def test_flow_and_step_logging():
    flow = IRFlow(
        name="f",
        description=None,
        steps=[IRFlowStep(name="noop", kind="script", target="", statements=[])],
    )
    program = IRProgram(models={"default": IRModel(name="default")}, agents={"helper": IRAgent(name="helper")}, frames={})
    engine, ctx = _engine(program)
    engine.run_flow(flow, ctx, initial_state={})
    logs = engine.frame_registry.query("event_log")
    kinds = [l.get("kind") for l in logs]
    assert "flow" in kinds
    assert "step" in kinds
    statuses = [l.get("status") for l in logs if l.get("kind") == "flow" and l.get("event_type") == "end"]
    assert any(s == "success" for s in statuses)


def test_step_error_logging():
    flow = IRFlow(
        name="f",
        description=None,
        steps=[IRFlowStep(name="bad", kind="frame_query", target="missing", params={})],
    )
    program = IRProgram(models={"default": IRModel(name="default")}, agents={}, frames={})
    engine, ctx = _engine(program)
    result = engine.run_flow(flow, ctx, initial_state={})
    assert result.errors
    logs = engine.frame_registry.query("event_log")
    assert any(l.get("kind") == "step" and l.get("event_type") == "error" for l in logs)
    assert any(l.get("kind") == "flow" and l.get("event_type") == "end" and l.get("status") == "error" for l in logs)


def test_ai_logging():
    flow = IRFlow(
        name="f",
        description=None,
        steps=[IRFlowStep(name="call", kind="ai", target="bot", params={})],
    )
    program = IRProgram(
        models={"default": IRModel(name="default")},
        agents={},
        ai_calls={"bot": ast_nodes.AICallDecl(name="bot", model_name="default")},
    )
    engine, ctx = _engine(program)
    engine.run_flow(flow, ctx, initial_state={})
    logs = engine.frame_registry.query("event_log")
    assert any(l.get("kind") == "ai" and l.get("event_type") == "start" for l in logs)
    assert any(l.get("kind") == "ai" and l.get("event_type") == "end" for l in logs)


def test_frame_crud_logging():
    flow = IRFlow(
        name="crud",
        description=None,
        steps=[
            IRFlowStep(
                name="insert",
                kind="frame_insert",
                target="logs",
                params={"values": {"message": ast_nodes.Literal(value="hello")}},
            ),
            IRFlowStep(
                name="update",
                kind="frame_update",
                target="logs",
                params={"where": {"message": ast_nodes.Literal(value="hello")}, "set": {"message": ast_nodes.Literal(value="hi")}},
            ),
            IRFlowStep(
                name="query",
                kind="frame_query",
                target="logs",
                params={"where": {"message": ast_nodes.Literal(value="hi")}},
            ),
            IRFlowStep(
                name="delete",
                kind="frame_delete",
                target="logs",
                params={"where": {"message": ast_nodes.Literal(value="hi")}},
            ),
        ],
    )
    program = IRProgram(
        models={"default": IRModel(name="default")},
        agents={},
        frames={"logs": IRFrame(name="logs", backend="memory", table="logs")},
    )
    engine, ctx = _engine(program)
    engine.run_flow(flow, ctx, initial_state={})
    logs = engine.frame_registry.query("event_log")
    ops = [l.get("operation") for l in logs if l.get("kind") == "frame"]
    assert {"insert", "update", "query", "delete"}.issubset(set(ops))
