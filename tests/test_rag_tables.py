from namel3ss.ir import (
    IRProgram,
    IRModel,
    IRAiCall,
    IRRagPipeline,
    IRRagPipelineStage,
    IRFrame,
    IRTableConfig,
)
from namel3ss.agent.engine import AgentRunner
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.flows.engine import FlowEngine
from namel3ss.runtime.context import ExecutionContext
from namel3ss.tools.registry import ToolRegistry
from namel3ss.flows.graph import FlowState


def _build_engine():
    program = IRProgram(
        models={"default": IRModel(name="default")},
        ai_calls={"bot": IRAiCall(name="bot", model_name="default")},
        frames={
            "orders": IRFrame(
                name="orders",
                source_kind="memory",
                table_config=IRTableConfig(
                    primary_key="id",
                    display_columns=["customer_name", "status", "total_amount"],
                ),
            )
        },
    )
    pipeline = IRRagPipeline(
        name="orders_support",
        stages=[
            IRRagPipelineStage(
                name="lookup",
                type="table_lookup",
                frame="orders",
                match_column="customer_name",
            ),
            IRRagPipelineStage(
                name="summaries",
                type="table_summarise",
                frame="orders",
                group_by="status",
            ),
            IRRagPipelineStage(name="answer", type="ai_answer", ai="bot"),
        ],
    )
    program.rag_pipelines["orders_support"] = pipeline
    registry = ModelRegistry()
    registry.register_model("default", provider_name=None)
    router = ModelRouter(registry)
    tool_registry = ToolRegistry()
    agent_runner = AgentRunner(program, registry, tool_registry, router)
    return FlowEngine(program=program, model_registry=registry, tool_registry=tool_registry, agent_runner=agent_runner, router=router)


def test_table_lookup_and_summarise(monkeypatch):
    engine = _build_engine()

    captured = {}

    async def fake_run_ai_stage(ai_name, payload, runtime_ctx, step_name, flow_name, base_context=None):
        captured["context"] = payload.get("context")
        return "done"

    monkeypatch.setattr(engine, "_run_ai_stage", fake_run_ai_stage)

    exec_ctx = ExecutionContext(app_name="app", request_id="req")
    runtime_ctx = engine._build_runtime_context(exec_ctx)
    runtime_ctx.frames.insert("orders", {"id": 1, "customer_name": "Alice", "status": "open", "total_amount": 42})
    runtime_ctx.frames.insert("orders", {"id": 2, "customer_name": "Bob", "status": "closed", "total_amount": 10})
    runtime_ctx.frames.insert("orders", {"id": 3, "customer_name": "Alice", "status": "open", "total_amount": 15})

    state = FlowState()
    result = engine._run_rag_pipeline(
        "orders_support", "Orders for Alice", state, runtime_ctx, exec_ctx, "flow", "step"
    )
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(result)
    finally:
        loop.close()

    assert captured.get("context")
    assert "Alice" in captured["context"]
    assert "open" in captured["context"]
