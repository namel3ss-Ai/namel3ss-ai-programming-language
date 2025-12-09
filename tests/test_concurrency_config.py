from types import SimpleNamespace

from namel3ss.flows.engine import FlowEngine


def test_max_parallel_tasks_respects_env(monkeypatch):
    monkeypatch.setenv("N3_MAX_PARALLEL_TASKS", "7")
    engine = FlowEngine(
        program=None,
        model_registry=SimpleNamespace(),
        tool_registry=SimpleNamespace(tools={}),
        agent_runner=SimpleNamespace(),
        router=SimpleNamespace(),
    )
    assert engine.max_parallel_tasks == 7
