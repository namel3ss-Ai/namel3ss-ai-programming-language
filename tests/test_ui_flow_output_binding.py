import asyncio

import pytest

from namel3ss import parser, ast_nodes
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.agent.engine import AgentRunner
from namel3ss.flows.engine import FlowEngine
from namel3ss.ir import IRFlow, IRFlowStep, IRModel, IRProgram, IRReturn, IRLet
from namel3ss.runtime.context import ExecutionContext
from namel3ss.tools.registry import ToolRegistry
from namel3ss.ui.components import UIComponentInstance, UIContext, UIEvent, UIEventHandler
from namel3ss.ui.runtime import UIEventRouter
from namel3ss.errors import ParseError


def _build_flow_engine(result_text: str = "hello") -> tuple[FlowEngine, AgentRunner, ToolRegistry, ExecutionContext]:
    flow = IRFlow(
        name="support_flow",
        description=None,
        steps=[
            IRFlowStep(
                name="first",
                kind="script",
                target="script",
                statements=[IRReturn(expr=ast_nodes.Literal(value=result_text))],
            ),
            IRFlowStep(
                name="second",
                kind="script",
                target="script",
                statements=[IRLet(name="later", expr=ast_nodes.Literal(value="stop"))],
            ),
        ],
    )
    program = IRProgram(flows={"support_flow": flow}, models={"default": IRModel(name="default")})
    model_registry = ModelRegistry()
    model_registry.register_model("default", provider_name=None)
    tool_registry = ToolRegistry()
    router = ModelRouter(model_registry)
    agent_runner = AgentRunner(program, model_registry, tool_registry, router)
    engine = FlowEngine(program, model_registry, tool_registry, agent_runner, router)
    ctx = ExecutionContext(app_name="demo", request_id="req-1")
    return engine, agent_runner, tool_registry, ctx


def _first_page(mod):
    return next(decl for decl in mod.declarations if isinstance(decl, ast_nodes.PageDecl))


def test_parse_output_to_state_in_button():
    mod = parser.parse_source(
        '''
page is "home" at "/":
  section "main":
    button "Ask":
      on click:
        do flow "support_flow" output to state.answer
'''
    )
    page = _first_page(mod)
    btn = page.layout[0].components[0]
    action = btn.handler.actions[0]
    assert action.output_target == "state.answer"


def test_parse_output_target_requires_state_prefix():
    src = (
        'page is "home":\n'
        '  section "main":\n'
        '    button "Ask":\n'
        '      on click:\n'
        '        do flow "support_flow" output to answer\n'
    )
    with pytest.raises(ParseError) as excinfo:
        parser.parse_source(src)
    assert "N3U-2302" in str(excinfo.value) or "N3L-PARSE-OUTPUT" in str(excinfo.value)


def test_flow_return_sets_result_and_stops_execution():
    engine, agent_runner, tool_registry, ctx = _build_flow_engine("hi")
    flow = engine.program.flows["support_flow"]
    result = asyncio.run(engine.run_flow_async(flow, ctx))
    assert result.result == "hi"
    assert result.state is not None
    assert "later" not in result.state.data
    assert any(step.step_name == "first" for step in result.steps)


def test_ui_event_binds_flow_output_to_state():
    engine, agent_runner, tool_registry, ctx = _build_flow_engine("hello")
    router = UIEventRouter(
        flow_engine=engine,
        agent_runner=agent_runner,
        tool_registry=tool_registry,
        rag_engine=None,
        job_queue=None,
        memory_engine=None,
        tracer=None,
        metrics=None,
    )
    handler = UIEventHandler(
        event="click",
        handler_kind="flow",
        target="support_flow",
        config={},
        output_target="state.answer",
    )
    comp = UIComponentInstance(id="btn1", kind="button", props={}, events=[handler])
    ui_ctx = UIContext(app_name="demo", page_name="home", metadata={"execution_context": ctx})
    event = UIEvent(component_id="btn1", event="click", payload={"state": {"user_input": "hi"}})
    result = asyncio.run(router.a_handle_event(comp, event, ui_ctx))
    assert result.success
    assert result.updated_state["state"]["answer"] == "hello"
    assert "flow" in result.updated_state
