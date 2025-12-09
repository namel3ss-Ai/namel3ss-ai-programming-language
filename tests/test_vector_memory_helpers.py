from types import SimpleNamespace

from namel3ss.memory.vector_helpers import retrieve_relevant_chunks, upsert_conversation_chunks
from namel3ss.runtime.vectorstores import VectorStoreRegistry


def _make_registry() -> VectorStoreRegistry:
    program = SimpleNamespace(
        vector_stores={
            "kb": SimpleNamespace(
                name="kb",
                backend="memory",
                frame="",
                text_column="text",
                id_column="id",
                embedding_model="deterministic",
                options={},
            )
        }
    )
    return VectorStoreRegistry(program)


def test_vector_upsert_and_retrieve_round_trip():
    registry = _make_registry()
    messages = [
        {"role": "user", "content": "hello world"},
        {"role": "assistant", "content": "acknowledged"},
    ]
    upsert_conversation_chunks(registry, "kb", messages, metadata={"session_id": "sess-1"})
    results = retrieve_relevant_chunks(registry, "kb", query="hello", top_k=3)
    assert results
    assert any(res.get("metadata", {}).get("session_id") == "sess-1" for res in results)
