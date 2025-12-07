import pytest

from namel3ss import parser, ast_nodes
from namel3ss.ir import ast_to_ir, IRError


def _first_flow(mod):
    return next(decl for decl in mod.declarations if isinstance(decl, ast_nodes.FlowDecl))


def test_vector_query_parses_legacy():
    mod = parser.parse_source(
        '''
flow "f1":
  step "retrieve":
    kind "vector_query"
    vector_store "kb"
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
flow "f1":
  step "retrieve":
    kind "vector_query"
    vector_store "missing"
    query_text "hi"
'''
    )
    with pytest.raises(IRError):
        ast_to_ir(mod)

