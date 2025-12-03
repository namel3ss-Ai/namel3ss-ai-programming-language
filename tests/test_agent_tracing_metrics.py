from namel3ss.agent.engine import AgentRunner
from namel3ss.agent.plan import AgentExecutionPlan, AgentStep
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.ir import IRAgent, IRModel, IRProgram
from namel3ss.metrics.tracker import MetricsTracker
from namel3ss.obs.tracer import Tracer
from namel3ss.runtime.context import ExecutionContext
from namel3ss.tools.registry import ToolRegistry


def test_tracer_records_agent_evaluation_and_metrics():
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
    tracer = Tracer()
    metrics = MetricsTracker()
    ctx = ExecutionContext(app_name="demo", request_id="r1", tracer=tracer, metrics=metrics)
    tracer.start_app("demo")
    tracer.start_page("agent")

    class SingleRunner(AgentRunner):
        def build_plan(self, agent, page_ai_fallback=None):
            return AgentExecutionPlan(steps=[AgentStep(name="ok", kind="tool", target="ok")])

    runner = SingleRunner(program, registry, tools, ModelRouter(registry))
    res = runner.run("helper", ctx)
    assert res.steps[0].evaluation is not None
    assert tracer.last_trace is not None
    assert tracer.last_trace.pages and tracer.last_trace.pages[0].agents
    snapshot = metrics.snapshot()
    assert snapshot["by_operation"]["agent_evaluation"]["count"] >= 1
