import pytest

from namel3ss import parser
from namel3ss.ast_nodes import VectorStoreDecl
from namel3ss.errors import ParseError
from namel3ss.ir import ast_to_ir


def parse_module(src: str):
    return parser.parse_source(src)


def test_legacy_model_header_rejected():
    with pytest.raises(ParseError) as excinfo:
        parse_module(
            '''
model "dummy":
  provider "openai_default"
'''
        )
    assert 'Use model is "dummy": instead.' in str(excinfo.value)


def test_frame_is_syntax_parses():
    mod = parse_module(
        '''
frame is "documents":
  source:
    backend is "default_db"
    table is "docs"
'''
    )
    frame = mod.declarations[0]
    assert frame.name == "documents"
    assert frame.backend == "default_db"
    assert frame.table == "docs"


def test_vector_store_both_syntaxes():
    mod = parse_module(
        '''
frame is "documents":
  source:
    backend is "memory"
    table is "docs"

vector_store is "kb":
  backend is "default_vector"
  frame is "documents"
  text_column is "content"
  id_column is "id"
  embedding_model is "default_embedding"

vector_store is "kb2":
  backend is "default_vector"
  frame is "documents"
  text_column is "content"
  id_column is "id"
  embedding_model is "default_embedding"
'''
    )
    vecs = [d for d in mod.declarations if isinstance(d, VectorStoreDecl)]
    assert len(vecs) == 2
    assert vecs[0].name == "kb"
    assert vecs[1].name == "kb2"
    ir = ast_to_ir(mod)
    assert "kb" in ir.vector_stores and "kb2" in ir.vector_stores


def test_vector_store_missing_backend_errors():
    mod = parse_module(
        '''
frame is "docs":
  source:
    backend is "memory"
    table is "docs"

vector_store is "kb":
  frame is "docs"
  text_column is "content"
  id_column is "id"
  embedding_model is "default_embedding"
'''
    )
    with pytest.raises(Exception):
        ast_to_ir(mod)
