from namel3ss.agent.engine import AgentRunner
from namel3ss.agent.models import AgentPlan, AgentStep
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ir import IRAgent, IRAiCall, IRModel, IRProgram
from namel3ss.runtime.context import ExecutionContext
from namel3ss.tools.registry import ToolRegistry


def build_basic_program() -> IRProgram:
    return IRProgram(
        agents={"helper": IRAgent(name="helper")},
        ai_calls={"ask": IRAiCall(name="ask", model_name="default")},
        models={"default": IRModel(name="default", provider=None)},
    )


def build_context() -> ExecutionContext:
    return ExecutionContext(app_name="demo", request_id="req-1")


def test_agent_runner_executes_ai_and_tool():
    program = build_basic_program()
    model_registry = ModelRegistry()
    model_registry.register_model("default", provider_name=None)
    tool_registry = ToolRegistry()
    from namel3ss.ai.router import ModelRouter

    class DummyTool:
        name = "echo"

        def run(self, **kwargs):
            return "ok"

    tool_registry.register(DummyTool())
    runner = AgentRunner(program, model_registry, tool_registry, ModelRouter(model_registry))
    result = runner.run("helper", build_context(), page_ai_fallback="ask")
    assert result.agent_name == "helper"
    assert any(step.success for step in result.steps)


def test_agent_runner_retries_on_failure():
    program = build_basic_program()
    model_registry = ModelRegistry()
    model_registry.register_model("default", provider_name=None)
    tool_registry = ToolRegistry()
    from namel3ss.ai.router import ModelRouter

    class FlakyTool:
        name = "flaky"

        def __init__(self):
            self.calls = 0

        def run(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("fail once")
            return "recovered"

    flaky = FlakyTool()
    tool_registry.register(flaky)

    class CustomRunner(AgentRunner):
        def build_plan(self, agent, page_ai_fallback=None):
            return AgentPlan(
                agent_name=agent.name,
                steps=[
                    AgentStep(
                        name="retry_tool",
                        kind="tool",
                        target="flaky",
                        max_retries=1,
                    )
                ],
            )

    runner = CustomRunner(program, model_registry, tool_registry, ModelRouter(model_registry))
    result = runner.run("helper", build_context())
    assert result.steps[0].success is True
    assert result.steps[0].retries == 1
