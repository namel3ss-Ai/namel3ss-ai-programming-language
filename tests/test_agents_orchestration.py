from namel3ss.agent.orchestration import route_and_run, run_supervisor_plan, run_debate_pattern
from namel3ss.agent.plan import AgentPlanResult, AgentStepResult
from namel3ss.runtime.context import ExecutionContext


class DummyRunner:
    def __init__(self):
        self.calls = []

    def run(self, agent_name, context, page_ai_fallback=None):
        self.calls.append(agent_name)
        if agent_name == "router":
            return AgentPlanResult(
                agent_name="router",
                steps=[],
                summary="route",
                final_output={"target_agent": "worker_b", "reason": "billing"},
                final_answer=None,
                ok=True,
                value={"target_agent": "worker_b", "reason": "billing"},
            )
        return AgentPlanResult(
            agent_name=agent_name,
            steps=[AgentStepResult(step_id="done", input={}, output={"value": f"{agent_name}-ok"}, success=True, error=None)],
            summary="done",
            final_output=f"{agent_name}-ok",
            final_answer=f"{agent_name}-ok",
            ok=True,
            value=f"{agent_name}-ok",
        )


def test_router_helper_routes_to_worker():
    runner = DummyRunner()
    ctx = ExecutionContext(app_name="app", request_id="req")
    decision, worker_result, router_result = route_and_run("router", ctx, runner)
    assert decision.target_agent == "worker_b"
    assert worker_result.final_answer == "worker_b-ok"
    assert router_result.ok is True
    assert runner.calls == ["router", "worker_b"]


def test_supervisor_plan_runs_workers_and_synthesizer():
    runner = DummyRunner()
    ctx = ExecutionContext(app_name="app", request_id="req2")
    plan = {"tasks": [{"agent_name": "worker_a", "description": "task 1"}, {"agent_name": "worker_b", "description": "task 2"}]}
    outcome = run_supervisor_plan("planner", ctx, runner, plan_value=plan, synthesizer_agent="worker_a")
    assert len(outcome.worker_results) == 2
    assert outcome.synthesizer_result is not None
    assert runner.calls[-1] == "worker_a"  # synthesizer invoked


def test_debate_pattern_runs_all_agents():
    runner = DummyRunner()
    ctx = ExecutionContext(app_name="app", request_id="req3")
    result = run_debate_pattern("q?", "worker_a", "worker_b", "worker_a", ctx, runner, team_runner=None)
    assert result["pro"].final_answer == "worker_a-ok"
    assert result["con"].final_answer == "worker_b-ok"
