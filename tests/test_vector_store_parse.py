import pytest

from namel3ss import parser
from namel3ss.ast_nodes import VectorStoreDecl
from namel3ss.ir import ast_to_ir


def parse_module(src: str):
    return parser.parse_source(src)


def test_frame_is_syntax_parses():
    mod = parse_module(
        '''
frame is "documents":
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
frame "documents":
  backend "memory"
  table "docs"

vector_store "kb":
  backend "default_vector"
  frame "documents"
  text_column "content"
  id_column "id"
  embedding_model "default_embedding"

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
frame "docs":
  backend "memory"
  table "docs"

vector_store "kb":
  frame "docs"
  text_column "content"
  id_column "id"
  embedding_model "default_embedding"
'''
    )
    with pytest.raises(Exception):
        ast_to_ir(mod)
