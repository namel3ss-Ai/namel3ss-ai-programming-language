from namel3ss.agent.engine import AgentRunner
from namel3ss.agent.plan import AgentExecutionPlan, AgentStep
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.ir import IRAgent, IRModel, IRProgram
from namel3ss.metrics.tracker import MetricsTracker
from namel3ss.runtime.context import ExecutionContext
from namel3ss.tools.registry import ToolRegistry


def build_context():
    return ExecutionContext(
        app_name="demo",
        request_id="req",
        tracer=None,
        metrics=MetricsTracker(),
    )


class FlakyTool:
    name = "flaky"

    def __init__(self):
        self.calls = 0

    def run(self, **kwargs):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("fail once")
        return "recovered"


def test_reflection_retries_tool_until_success():
    program = IRProgram(
        agents={"helper": IRAgent(name="helper")},
        models={"m": IRModel(name="m", provider=None)},
    )
    registry = ModelRegistry()
    registry.register_model("m", None)
    tools = ToolRegistry()
    flaky = FlakyTool()
    tools.register(flaky)
    runner = AgentRunner(program, registry, tools, ModelRouter(registry))

    class CustomRunner(AgentRunner):
        def build_plan(self, agent, page_ai_fallback=None):
            return AgentExecutionPlan(
                steps=[
                    AgentStep(name="retry_tool", kind="tool", target="flaky", max_retries=1),
                ],
                max_retries_per_step=1,
                agent_name=agent.name,
            )

    runner = CustomRunner(program, registry, tools, ModelRouter(registry))
    result = runner.run("helper", build_context())
    assert len(result.steps) == 1
    final_step = result.steps[0]
    assert final_step.success is True
    assert final_step.retries == 1


def test_reflection_stops_when_budget_exceeded():
    program = IRProgram(
        agents={"helper": IRAgent(name="helper")},
        models={"m": IRModel(name="m", provider=None)},
    )
    registry = ModelRegistry()
    registry.register_model("m", None)
    tools = ToolRegistry()

    class OkTool:
        name = "ok"

        def run(self, **kwargs):
            return "ok"

    tools.register(OkTool())
    ctx = build_context()
    # Inflate cost to trigger budget stop in deterministic evaluator.
    for _ in range(10):
        ctx.metrics.record_ai_call(provider="dummy", cost=1.0)
    runner = AgentRunner(program, registry, tools, ModelRouter(registry))

    class BudgetRunner(AgentRunner):
        def build_plan(self, agent, page_ai_fallback=None):
            return AgentExecutionPlan(
                steps=[AgentStep(name="only", kind="tool", target="ok")],
                max_retries_per_step=0,
            )

    runner = BudgetRunner(program, registry, tools, ModelRouter(registry))
    res = runner.run("helper", ctx)
    assert res.steps[0].evaluation is not None
    assert res.steps[0].evaluation.verdict == "stop"
    assert "halted" in (res.summary or "")


def test_retry_bound_respected_on_failures():
    program = IRProgram(
        agents={"helper": IRAgent(name="helper")},
        models={"m": IRModel(name="m", provider=None)},
    )
    registry = ModelRegistry()
    registry.register_model("m", None)
    tools = ToolRegistry()

    class AlwaysFail:
        name = "fail"

        def run(self, **kwargs):
            raise RuntimeError("always")

    tools.register(AlwaysFail())

    class FailRunner(AgentRunner):
        def build_plan(self, agent, page_ai_fallback=None):
            return AgentExecutionPlan(
                steps=[AgentStep(name="fail", kind="tool", target="fail", max_retries=1)],
                max_retries_per_step=1,
            )

    runner = FailRunner(program, registry, tools, ModelRouter(registry))
    res = runner.run("helper", build_context())
    assert res.steps[0].success is False
    assert res.steps[0].retries == 1
    assert res.steps[0].evaluation.verdict in {"stop", "retry"}
