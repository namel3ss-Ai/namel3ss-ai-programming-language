import pytest

from namel3ss.rag.factory import VectorStoreFactory
from namel3ss.rag.vectorstores.memory import InMemoryVectorStore
from namel3ss.secrets.manager import SecretsManager
from namel3ss.errors import Namel3ssError


def test_factory_returns_memory_store():
    factory = VectorStoreFactory(SecretsManager(env={}))
    store = factory.get("memory", {"name": "idx"})
    assert isinstance(store, InMemoryVectorStore)


def test_factory_pgvector_requires_dsn():
    factory = VectorStoreFactory(SecretsManager(env={}))
    with pytest.raises(Namel3ssError):
        factory.get("pgvector", {"name": "idx"})
