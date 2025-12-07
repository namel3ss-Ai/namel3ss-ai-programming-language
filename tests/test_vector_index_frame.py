import asyncio

import pytest

from namel3ss import parser
from namel3ss.ast_nodes import FlowDecl
from namel3ss.flows.engine import FlowEngine
from namel3ss.flows.graph import FlowState
from namel3ss.ir import ast_to_ir
from namel3ss.agent.engine import AgentRunner
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.metrics.tracker import MetricsTracker
from namel3ss.runtime.context import ExecutionContext
from namel3ss.tools.registry import ToolRegistry
from namel3ss.runtime.vectorstores import InMemoryVectorBackend, VectorStoreRegistry, EmbeddingClient


def test_parse_vector_index_step_both_syntax():
    module = parser.parse_source(
        '''
flow "index_all_documents":
  step "index":
    kind "vector_index_frame"
    vector_store "kb"

flow is "index_filtered_documents":
  step is "index":
    kind is "vector_index_frame"
    vector_store is "kb"
    where:
      project_id: state.project_id
'''
    )
    flows = [d for d in module.declarations if isinstance(d, FlowDecl)]
    assert len(flows) == 2
    f1, f2 = flows
    assert f1.steps[0].kind == "vector_index_frame"
    assert f1.steps[0].params.get("vector_store") == "kb"
    assert f2.steps[0].kind == "vector_index_frame"
    assert "project_id" in f2.steps[0].params.get("where", {})


class FakeEmbeddingClient(EmbeddingClient):
    def __init__(self):
        pass

    def embed(self, model_name, texts):
        return [[len(t) or 0.0] for t in texts]


def _build_engine(ir):
    registry = ModelRegistry()
    registry.register_model("default", provider_name=None)
    router = ModelRouter(registry)
    tool_registry = ToolRegistry()
    agent_runner = AgentRunner(ir, registry, tool_registry, router)
    metrics = MetricsTracker()
    engine = FlowEngine(
        program=ir,
        model_registry=registry,
        tool_registry=tool_registry,
        agent_runner=agent_runner,
        router=router,
        metrics=metrics,
    )
    return engine


def test_vector_index_flow_indexes_rows():
    module = parser.parse_source(
        '''
frame "docs":
  backend "memory"
  table "docs"

vector_store "kb":
  backend "memory"
  frame "docs"
  text_column "content"
  id_column "id"
  embedding_model "default_embedding"

flow "index_docs":
  step "insert_one":
    kind "frame_insert"
    frame "docs"
    values:
      id: 1
      content: "hello"
      project_id: 42
  step "insert_two":
    kind "frame_insert"
    frame "docs"
    values:
      id: 2
      content: "bye"
      project_id: 99
  step "index":
    kind "vector_index_frame"
    vector_store "kb"
    where:
      project_id: 42
'''
    )
    ir = ast_to_ir(module)
    engine = _build_engine(ir)
    last_ctx = {}

    orig_build = engine._build_runtime_context

    def patched_build(ctx):
        runtime_ctx = orig_build(ctx)
        # share a deterministic backend and embedding client
        vec_registry: VectorStoreRegistry = runtime_ctx.vectorstores
        backend = InMemoryVectorBackend()
        vec_registry.backends["memory"] = backend
        vec_registry.backends["default_vector"] = backend
        vec_registry.embedding_client = FakeEmbeddingClient()
        last_ctx["ctx"] = runtime_ctx
        return runtime_ctx

    engine._build_runtime_context = patched_build  # type: ignore

    exec_ctx = ExecutionContext(app_name="test", request_id="req")
    flow = ir.flows["index_docs"]
    result = engine.run_flow(flow, exec_ctx, initial_state={})
    assert result.state is not None
    # step output should equal number of indexed rows (1)
    assert result.state.get("last_output") == 1
    backend = last_ctx["ctx"].vectorstores.backends["memory"]
    bucket = backend._store.get("kb")  # type: ignore[attr-defined]
    assert bucket is not None
    assert len(bucket) == 1
    assert bucket[0][0] == "1"


def test_vector_index_unknown_store_errors():
    module = parser.parse_source(
        '''
frame "docs":
  backend "memory"
  table "docs"

flow "index_docs":
  step "index":
    kind "vector_index_frame"
    vector_store "missing"
'''
    )
    with pytest.raises(Exception):
        ir = ast_to_ir(module)
        engine = _build_engine(ir)
        exec_ctx = ExecutionContext(app_name="test", request_id="req")
        engine.run_flow(ir.flows["index_docs"], exec_ctx, initial_state={})
