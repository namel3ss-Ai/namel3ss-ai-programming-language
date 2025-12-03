from namel3ss.agent.engine import AgentRunner
from namel3ss.ai.registry import ModelRegistry
from namel3ss.flows.engine import FlowEngine
from namel3ss.ir import IRAgent, IRAiCall, IRFlow, IRFlowStep, IRModel, IRProgram
from namel3ss.runtime.context import ExecutionContext
from namel3ss.tools.registry import ToolRegistry
from namel3ss.ai.router import ModelRouter


def build_program_with_flow() -> IRProgram:
    return IRProgram(
        ai_calls={"ask": IRAiCall(name="ask", model_name="default")},
        agents={"helper": IRAgent(name="helper")},
        models={"default": IRModel(name="default")},
        flows={
            "pipeline": IRFlow(
                name="pipeline",
                description=None,
                steps=[
                    IRFlowStep(name="call_ai", kind="ai", target="ask"),
                    IRFlowStep(name="call_agent", kind="agent", target="helper"),
                ],
            )
        },
    )


def build_registries(program: IRProgram):
    model_registry = ModelRegistry()
    model_registry.register_model("default", provider_name=None)
    tool_registry = ToolRegistry()
    # Minimal agent runner and flow engine will use registries
    agent_runner = AgentRunner(program, model_registry, tool_registry, ModelRouter(model_registry))
    return model_registry, tool_registry, agent_runner


def test_flow_engine_runs_steps():
    program = build_program_with_flow()
    model_registry, tool_registry, agent_runner = build_registries(program)
    engine = FlowEngine(program, model_registry, tool_registry, agent_runner, ModelRouter(model_registry))
    context = ExecutionContext(app_name="demo", request_id="req-1")
    result = engine.run_flow(program.flows["pipeline"], context)
    assert result.flow_name == "pipeline"
    assert all(step.success for step in result.steps)


def test_flow_engine_handles_missing_tool_failure():
    program = build_program_with_flow()
    # inject a failing step
    program.flows["pipeline"].steps.append(
        IRFlowStep(name="missing_tool", kind="tool", target="not_there")
    )
    model_registry, tool_registry, agent_runner = build_registries(program)
    engine = FlowEngine(program, model_registry, tool_registry, agent_runner, ModelRouter(model_registry))
    context = ExecutionContext(app_name="demo", request_id="req-2")
    result = engine.run_flow(program.flows["pipeline"], context)
    assert result.steps[-1].success is False
