from __future__ import annotations

from typing import Dict

from .vectorstores.base import VectorStore
from .vectorstores.memory import InMemoryVectorStore
from .vectorstores.pgvector import PGVectorStore
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
        if backend == "memory":
            store = InMemoryVectorStore()
        elif backend == "pgvector":
            dsn = config.get("dsn") or self.secrets.get("N3_PGVECTOR_DSN")
            if not dsn:
                raise Namel3ssError("PGVector backend requested but N3_PGVECTOR_DSN not set")
            store = PGVectorStore(dsn=dsn, table=config.get("table", "rag_items"))
        else:
            raise Namel3ssError(f"Unsupported vector store backend '{backend}'")
        self._cache[key] = store
        return store
