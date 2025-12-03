from __future__ import annotations

from typing import Dict

from .vectorstores.base import VectorStore
from .vectorstores.memory import InMemoryVectorStore
from .vectorstores.pgvector import PGVectorStore
from .vectorstores.faiss import FAISSVectorStore
from ..secrets.manager import SecretsManager
from ..errors import Namel3ssError


class VectorStoreFactory:
    def __init__(self, secrets: SecretsManager) -> None:
        self.secrets = secrets
        self._cache: Dict[str, VectorStore] = {}

    def get(self, backend: str, config: dict) -> VectorStore:
        key = f"{backend}:{config.get('name') or config.get('collection', '')}"
        if key in self._cache:
            return self._cache[key]
        backend = backend.lower()
        if backend == "memory":
            store = InMemoryVectorStore()
        elif backend == "pgvector":
            dsn = config.get("dsn") or self.secrets.get_pgvector_dsn()
            table = config.get("table") or self.secrets.get_pgvector_table(config.get("name") or config.get("collection", "rag_items"))
            if not dsn:
                raise Namel3ssError("PGVector backend requested but DSN not set")
            store = PGVectorStore(dsn=dsn, table=table)
        elif backend == "faiss":
            dimension = config.get("dimension")
            if dimension is None:
                raise Namel3ssError("FAISS backend requires 'dimension'")
            store = FAISSVectorStore(dimension=dimension)
        else:
            raise Namel3ssError(f"Unsupported vector store backend '{backend}'")
        self._cache[key] = store
        return store
