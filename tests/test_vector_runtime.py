from namel3ss.ir import ast_to_ir
from namel3ss import parser
from namel3ss.runtime.vectorstores import VectorStoreRegistry, InMemoryVectorBackend, EmbeddingClient


class FakeEmbeddingClient(EmbeddingClient):
    def __init__(self):
        pass

    def embed(self, model_name, texts):
        # deterministic simple vectors: length of text
        return [[len(t)] for t in texts]


def build_registry():
    mod = parser.parse_source(
        '''
frame "docs":
  backend "memory"
  table "docs"

vector_store "kb":
  backend "memory"
  frame "docs"
  text_column "content"
  id_column "id"
  embedding_model "fake"
'''
    )
    ir = ast_to_ir(mod)
    reg = VectorStoreRegistry(ir)
    reg.embedding_client = FakeEmbeddingClient()
    # share backend across memory and default_vector keys
    reg.backends["memory"] = InMemoryVectorBackend()
    return reg


def test_vector_index_and_query():
    reg = build_registry()
    reg.index_texts("kb", ids=["1", "2"], texts=["hello", "world!"])
    results = reg.query("kb", query_text="hi", top_k=1)
    assert results
    assert results[0]["id"] in {"1", "2"}


def test_query_empty_store():
    reg = build_registry()
    results = reg.query("kb", query_text="nothing", top_k=3)
    assert results == []
