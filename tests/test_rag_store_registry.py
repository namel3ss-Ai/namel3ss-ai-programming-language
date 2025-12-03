from namel3ss.rag.store_registry import VectorStoreRegistry
from namel3ss.rag.index_config import RAGIndexConfig
from namel3ss.secrets.manager import SecretsManager
from namel3ss.rag.vectorstores.memory import InMemoryVectorStore
from namel3ss.rag.vectorstores.faiss import FAISSVectorStore, faiss
from namel3ss.errors import Namel3ssError
import pytest


def test_registry_defaults_to_memory():
    registry = VectorStoreRegistry(secrets=SecretsManager(env={}))
    store = registry.get_store(RAGIndexConfig(name="docs"))
    assert isinstance(store, InMemoryVectorStore)


@pytest.mark.skipif(faiss is None, reason="faiss not installed")
def test_registry_can_build_faiss():
    env = {"N3_RAG_INDEX_DOCS_BACKEND": "faiss"}
    registry = VectorStoreRegistry(secrets=SecretsManager(env=env))
    store = registry.get_store(RAGIndexConfig(name="docs", options={"dimension": 3}))
    assert isinstance(store, FAISSVectorStore)


def test_registry_pgvector_missing_dsn_raises():
    env = {"N3_RAG_INDEX_DOCS_BACKEND": "pgvector"}
    registry = VectorStoreRegistry(secrets=SecretsManager(env=env))
    with pytest.raises(Namel3ssError):
        registry.get_store(RAGIndexConfig(name="docs"))
