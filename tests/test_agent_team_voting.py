from namel3ss.agent.teams import AgentTeamRunner
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.ir import IRAgent, IRAiCall, IRModel, IRProgram
from namel3ss.runtime.context import ExecutionContext
from namel3ss.tools.registry import ToolRegistry
from namel3ss.obs.tracer import Tracer


def test_team_runner_votes_and_traces():
    program = IRProgram(
        agents={"a1": IRAgent(name="a1"), "a2": IRAgent(name="a2")},
        ai_calls={"ask": IRAiCall(name="ask", model_name="m")},
        models={"m": IRModel(name="m", provider=None)},
    )
    registry = ModelRegistry()
    registry.register_model("m", None)
    router = ModelRouter(registry)
    tools = ToolRegistry()
    tracer = Tracer()
    ctx = ExecutionContext(app_name="team", request_id="req", tracer=tracer, metrics=None)
    tracer.start_app("team-app")

    runner = AgentTeamRunner(program, registry, router, tools)
    result = runner.run_team(["a1", "a2"], "task", ctx)
    assert "winner" in (result.summary or "")
    assert len(result.messages) == 2
    assert tracer.last_trace is not None
    # Team vote recorded
    assert tracer.last_trace.teams
