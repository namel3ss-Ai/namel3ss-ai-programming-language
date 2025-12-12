import pytest

from namel3ss import parser
from namel3ss.agent.engine import AgentRunner
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.flows.engine import FlowEngine
from namel3ss.ir import ast_to_ir
from namel3ss.runtime.context import ExecutionContext
from namel3ss.tools.registry import ToolRegistry
from namel3ss.errors import Namel3ssError


def test_vector_query_runtime_builds_context(monkeypatch):
    source = '''
frame is "docs":
  backend is "memory"
  table is "docs"

vector_store is "kb":
  backend "memory"
  frame is "docs"
  text_column "content"
  id_column "id"
  embedding_model is "fake"

flow is "index_and_query":
  step is "insert":
    kind "frame_insert"
    frame is "docs"
    values:
      id: "1"
      content: "hello world"
  step is "index":
    kind "vector_index_frame"
    vector_store is "kb"
  step is "retrieve":
    kind "vector_query"
    vector_store is "kb"
    query_text "hello"
    top_k 1
'''
    mod = parser.parse_source(source)
    ir = ast_to_ir(mod)
    model_registry = ModelRegistry()
    model_registry.register_model("default", provider_name=None)
    tool_registry = ToolRegistry()
    router = ModelRouter(model_registry)
    agent_runner = AgentRunner(ir, model_registry, tool_registry, router)
    engine = FlowEngine(ir, model_registry, tool_registry, agent_runner, router)

    # deterministic embeddings: length of text
    engine.vector_registry.embedding_client.embed = lambda model, texts: [[len(t)] for t in texts]
    # share backend for memory/default_vector consistency
    if "memory" in engine.vector_registry.backends:
        engine.vector_registry.backends["memory"] = engine.vector_registry.backends.get("memory")

    ctx = ExecutionContext(app_name="test", request_id="req")
    result = engine.run_flow(ir.flows["index_and_query"], ctx)

    output = result.state.data.get("step.retrieve.output")
    assert output
    assert output.get("matches")
    assert "Document" in (output.get("context") or "")


def test_vector_query_rejects_bad_top_k(monkeypatch):
    source = '''
frame is "docs":
  backend is "memory"
  table is "docs"

vector_store is "kb":
  backend "memory"
  frame is "docs"
  text_column "content"
  id_column "id"
  embedding_model is "fake"

flow is "index_and_query":
  step is "insert":
    kind "frame_insert"
    frame is "docs"
    values:
      id: "1"
      content: "hello world"
  step is "index":
    kind "vector_index_frame"
    vector_store is "kb"
  step is "retrieve":
    kind "vector_query"
    vector_store is "kb"
    query_text "hello"
    top_k "bad"
'''
    mod = parser.parse_source(source)
    with pytest.raises(Namel3ssError) as excinfo:
        ast_to_ir(mod)
    assert "Top_k for step 'retrieve'" in str(excinfo.value)
