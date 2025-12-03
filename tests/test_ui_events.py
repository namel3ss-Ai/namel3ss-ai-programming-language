import asyncio

from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.agent.engine import AgentRunner
from namel3ss.flows.engine import FlowEngine
from namel3ss.ir import IRAgent, IRFlow, IRFlowStep, IRAiCall, IRModel, IRProgram
from namel3ss.ui.components import UIComponentInstance, UIEvent, UIEventHandler, UIContext
from namel3ss.ui.runtime import UIEventRouter
from namel3ss.ui.validation import validate_form
from namel3ss.tools.registry import ToolRegistry
from namel3ss.runtime.context import ExecutionContext


def _build_runtime():
    program = IRProgram(
        flows={
            "pipeline": IRFlow(
                name="pipeline",
                description=None,
                steps=[
                    IRFlowStep(name="call", kind="ai", target="ask"),
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
    agent_runner = AgentRunner(program, model_registry, tool_registry, router)
    flow_engine = FlowEngine(program, model_registry, tool_registry, agent_runner, router)
    ctx = ExecutionContext(app_name="ui", request_id="req-1")
    return flow_engine, agent_runner, tool_registry, ctx


def test_validation_blocks_submit():
    fields = [{"id": "email", "required": True, "regex": r".+@.+"}]
    valid, errors = validate_form(fields, {"email": ""})
    assert not valid
    assert "email" in errors


def test_ui_event_dispatches_flow():
    flow_engine, agent_runner, tool_registry, exec_ctx = _build_runtime()
    router = UIEventRouter(
        flow_engine=flow_engine,
        agent_runner=agent_runner,
        tool_registry=tool_registry,
        rag_engine=None,
        job_queue=None,
        memory_engine=None,
        tracer=None,
        metrics=None,
    )
    comp = UIComponentInstance(
        id="form1",
        kind="form",
        props={"fields": [{"id": "name", "required": True}]},
        events=[UIEventHandler(event="submit", handler_kind="flow", target="pipeline", config={})],
    )
    ui_ctx = UIContext(app_name="demo", page_name="home", metadata={"execution_context": exec_ctx})
    event = UIEvent(component_id="form1", event="submit", payload={"name": "Ada"})
    result = asyncio.run(router.a_handle_event(comp, event, ui_ctx))
    assert result.success
    assert "flow" in result.updated_state
