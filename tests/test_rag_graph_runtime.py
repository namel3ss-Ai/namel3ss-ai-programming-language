from namel3ss.rag.graph import GraphEngine, GraphData, GraphNode, GraphEdge
from namel3ss.ir import (
    IRProgram,
    IRModel,
    IRAiCall,
    IRAgent,
    IRGraph,
    IRGraphSummary,
    IRRagPipeline,
    IRRagPipelineStage,
)
from namel3ss.agent.engine import AgentRunner
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.flows.engine import FlowEngine
from namel3ss.runtime.context import ExecutionContext
from namel3ss.tools.registry import ToolRegistry
from namel3ss.flows.graph import FlowState


class FakeGraphEngine(GraphEngine):
    def __init__(self) -> None:
        super().__init__({})
        data = GraphData(
            nodes={
                "a": GraphNode(id="a", text="ComponentA"),
                "b": GraphNode(id="b", text="ComponentB"),
            },
            edges=[GraphEdge(source="a", target="b", relation="depends_on")],
        )
        self._graphs["g"] = data
        self.summary_defs["gs"] = IRGraphSummary(name="gs", graph="g", method="community")
        self._summaries["gs"] = [{"text": "Summary of ComponentA, ComponentB", "nodes": ["a", "b"]}]

    def query(self, graph_name: str, query_text: str, max_hops: int = 2, max_nodes: int = 25, strategy: str | None = None, frames=None):
        return [{"text": "Node ComponentA depends_on ComponentB"}]

    def lookup_summary(self, summary_name: str, query_text: str, top_k: int = 5, frames=None):
        return [{"text": "Summary of ComponentA, ComponentB"}]


def _build_engine() -> FlowEngine:
    program = IRProgram(
        models={"default": IRModel(name="default")},
        ai_calls={"bot": IRAiCall(name="bot", model_name="default")},
        agents={"helper": IRAgent(name="helper")},
        graphs={"g": IRGraph(name="g", source_frame="docs", id_column="id", text_column="text")},
        graph_summaries={"gs": IRGraphSummary(name="gs", graph="g")},
    )
    pipeline = IRRagPipeline(
        name="graph_pipe",
        stages=[
            IRRagPipelineStage(name="gq", type="graph_query", graph="g"),
            IRRagPipelineStage(name="gs", type="graph_summary_lookup", graph_summary="gs", top_k=None),
            IRRagPipelineStage(name="answer", type="ai_answer", ai="bot"),
        ],
    )
    program.rag_pipelines["graph_pipe"] = pipeline
    registry = ModelRegistry()
    registry.register_model("default", provider_name=None)
    router = ModelRouter(registry)
    tool_registry = ToolRegistry()
    agent_runner = AgentRunner(program, registry, tool_registry, router)
    return FlowEngine(program=program, model_registry=registry, tool_registry=tool_registry, agent_runner=agent_runner, router=router)


def test_graph_rag_pipeline_adds_context(monkeypatch):
    engine = _build_engine()

    captured = {}

    async def fake_run_ai_stage(ai_name, payload, runtime_ctx, step_name, flow_name, base_context=None):
        captured["context"] = payload.get("context")
        return "done"

    monkeypatch.setattr(engine, "_run_ai_stage", fake_run_ai_stage)

    exec_ctx = ExecutionContext(app_name="app", request_id="req")
    runtime_ctx = engine._build_runtime_context(exec_ctx)
    runtime_ctx.graph_engine = FakeGraphEngine()
    state = FlowState()
    result = engine._run_rag_pipeline("graph_pipe", "question about ComponentA", state, runtime_ctx, exec_ctx, "flow", "step")
    # _run_rag_pipeline is async; run through asyncio loop
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        output = loop.run_until_complete(result)
    finally:
        loop.close()
    assert "Node ComponentA" in output.get("context", "")
    assert "Summary of ComponentA" in output.get("context", "")
    assert captured["context"] and "Summary" in captured["context"]
