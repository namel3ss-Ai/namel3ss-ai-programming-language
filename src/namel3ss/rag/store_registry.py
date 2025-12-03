from __future__ import annotations

from typing import Dict, Optional

from .index_config import RAGIndexConfig
from .factory import VectorStoreFactory
from .vectorstores.base import VectorStore
from ..secrets.manager import SecretsManager


class VectorStoreRegistry:
    def __init__(self, secrets: Optional[SecretsManager] = None) -> None:
        self.secrets = secrets or SecretsManager()
        self.factory = VectorStoreFactory(self.secrets)
        self._stores: Dict[str, VectorStore] = {}

    def get_store(self, index: RAGIndexConfig) -> VectorStore:
        backend = self.secrets.get_rag_index_backend(index.name) or index.backend
        key = f"{backend}:{index.name}"
        if key in self._stores:
            return self._stores[key]
        cfg = {
            "name": index.name,
            "collection": index.collection,
            "dsn": index.dsn,
            "table": self.secrets.get_pgvector_table(index.name) or index.collection,
            "dimension": index.options.get("dimension") if hasattr(index, "options") else None,
        }
        store = self.factory.get(backend, cfg)
        self._stores[key] = store
        return store
