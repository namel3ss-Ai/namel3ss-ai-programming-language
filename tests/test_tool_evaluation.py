from namel3ss.agent.engine import AgentRunner
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.flows.engine import FlowEngine
from namel3ss.ir import (
    IRProgram,
    IRTool,
    IRToolEvaluation,
    IRFrame,
    IRTableConfig,
)
from namel3ss.runtime.context import ExecutionContext
from namel3ss.tools.eval import run_tool_evaluation
from namel3ss.tools.registry import ToolRegistry


def double(value):
    return value * 2


def _build_engine_with_tool_eval():
    program = IRProgram()
    program.tools["doubler"] = IRTool(
        name="doubler",
        kind="local_function",
        function="test_tool_evaluation.double",
        input_fields=["value"],
    )
    program.frames["cases"] = IRFrame(
        name="cases",
        source_kind="memory",
        select_cols=["value", "expected_status", "expected_text"],
        table_config=IRTableConfig(primary_key="value", display_columns=["value"]),
    )
    program.tool_evaluations["doubler_eval"] = IRToolEvaluation(
        name="doubler_eval",
        tool="doubler",
        dataset_frame="cases",
        input_mapping={"value": "value"},
        expected_status_column="expected_status",
        expected_body_column="expected_text",
        metrics=["success_rate", "latency_ms", "error_rate"],
    )
    registry = ModelRegistry()
    registry.register_model("default", provider_name=None)
    router = ModelRouter(registry)
    tool_registry = ToolRegistry()
    agent_runner = AgentRunner(program, registry, tool_registry, router)
    engine = FlowEngine(program=program, model_registry=registry, tool_registry=tool_registry, agent_runner=agent_runner, router=router)
    return engine


def test_tool_evaluation_runs(monkeypatch):
    engine = _build_engine_with_tool_eval()
    exec_ctx = ExecutionContext(app_name="app", request_id="req")
    engine.frame_registry.insert("cases", {"value": 2, "expected_status": None, "expected_text": "4"})
    engine.frame_registry.insert("cases", {"value": 3, "expected_status": None, "expected_text": "6"})

    eval_cfg = engine.program.tool_evaluations["doubler_eval"]
    result = run_tool_evaluation(engine.program, eval_cfg, engine)

    assert result.metrics.get("success_rate", 0) == 1.0
    assert result.num_rows == 2
