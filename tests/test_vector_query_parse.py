import pytest

from namel3ss import parser, ast_nodes
from namel3ss.ir import ast_to_ir, IRError


def _first_flow(mod):
    return next(decl for decl in mod.declarations if isinstance(decl, ast_nodes.FlowDecl))


def test_vector_query_parses_legacy():
    mod = parser.parse_source(
        '''
flow is "f1":
  step is "retrieve":
    kind "vector_query"
    vector_store is "kb"
    query_text "hello"
    top_k 3
'''
    )
    flow = _first_flow(mod)
    step = flow.steps[0]
    assert step.kind == "vector_query"
    assert step.params.get("vector_store") == "kb"
    assert step.params.get("query_text") is not None
    assert step.params.get("top_k") is not None


def test_vector_query_parses_is_syntax():
    mod = parser.parse_source(
        '''
flow is "f2":
  step is "retrieve":
    kind is "vector_query"
    vector_store is "kb"
    query_text is state.question
    top_k 5
'''
    )
    flow = _first_flow(mod)
    step = flow.steps[0]
    assert step.kind == "vector_query"
    assert step.params.get("vector_store") == "kb"
    assert step.params.get("query_text") is not None
    assert step.params.get("top_k") is not None


def test_vector_query_requires_declared_vector_store():
    mod = parser.parse_source(
        '''
flow is "f1":
  step is "retrieve":
    kind "vector_query"
    vector_store is "missing"
    query_text "hi"
'''
    )
    with pytest.raises(IRError):
        ast_to_ir(mod)


def test_vector_query_requires_query_text():
    mod = parser.parse_source(
        '''
frame is "docs":
  backend is "memory"
  table is "docs"

vector_store is "kb":
  backend is "memory"
  frame is "docs"
  text_column is "content"
  id_column is "id"
  embedding_model is "default_embedding"

flow is "f3":
  step is "retrieve":
    kind is "vector_query"
    vector_store is "kb"
'''
    )
    with pytest.raises(IRError) as exc:
        ast_to_ir(mod)
    assert "must define 'query_text'" in str(exc.value)
