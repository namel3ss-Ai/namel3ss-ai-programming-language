from namel3ss.ir import (
    IRProgram,
    IRModel,
    IRAiCall,
    IRRagPipeline,
    IRRagPipelineStage,
    IRFrame,
    IRVectorStore,
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
            "products": IRFrame(
                name="products",
                source_kind="memory",
                table_config=IRTableConfig(
                    primary_key="product_id",
                    display_columns=["name", "category"],
                    text_column="description",
                    image_column="image_url",
                ),
            )
        },
        vector_stores={
            "media_vectors": IRVectorStore(
                name="media_vectors",
                backend="memory",
                frame="products",
                text_column="description",
                id_column="product_id",
                embedding_model="default_embedding",
                metadata_columns=[],
                options={},
            )
        },
    )
    pipeline = IRRagPipeline(
        name="product_qa",
        stages=[
            IRRagPipelineStage(
                name="embed",
                type="multimodal_embed",
                frame="products",
                image_column="image_url",
                text_column="description",
                output_vector_store="media_vectors",
            ),
            IRRagPipelineStage(
                name="retrieve",
                type="vector_retrieve",
                vector_store="media_vectors",
                top_k=None,
            ),
            IRRagPipelineStage(name="answer", type="ai_answer", ai="bot"),
        ],
    )
    program.rag_pipelines["product_qa"] = pipeline
    registry = ModelRegistry()
    registry.register_model("default", provider_name=None)
    router = ModelRouter(registry)
    tool_registry = ToolRegistry()
    agent_runner = AgentRunner(program, registry, tool_registry, router)
    return FlowEngine(program=program, model_registry=registry, tool_registry=tool_registry, agent_runner=agent_runner, router=router)


def test_multimodal_embed_and_retrieve(monkeypatch):
    engine = _build_engine()

    captured = {}

    async def fake_run_ai_stage(ai_name, payload, runtime_ctx, step_name, flow_name, base_context=None):
        captured["context"] = payload.get("context")
        return "done"

    monkeypatch.setattr(engine, "_run_ai_stage", fake_run_ai_stage)

    exec_ctx = ExecutionContext(app_name="app", request_id="req")
    runtime_ctx = engine._build_runtime_context(exec_ctx)

    # stub embedding to deterministic vectors
    monkeypatch.setattr(
        runtime_ctx.vectorstores.embedding_client,
        "embed",
        lambda model, texts: [[1.0 for _ in range(1)]] * len(texts),
    )

    runtime_ctx.frames.insert(
        "products",
        {"product_id": "p1", "name": "CameraX", "category": "camera", "description": "High-res camera", "image_url": "img://camera"},
    )
    runtime_ctx.frames.insert(
        "products",
        {"product_id": "p2", "name": "SpeakerY", "category": "audio", "description": "Loud speaker", "image_url": "img://speaker"},
    )

    state = FlowState()
    result = engine._run_rag_pipeline(
        "product_qa", "Tell me about Camera", state, runtime_ctx, exec_ctx, "flow", "step"
    )
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(result)
    finally:
        loop.close()

    assert captured.get("context")
    assert "camera" in captured["context"].lower()
