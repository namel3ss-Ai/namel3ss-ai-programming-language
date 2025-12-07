from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional

from ..errors import Namel3ssError
from ..ir import IRProgram
from ..rag.embedding_registry import EmbeddingProviderRegistry
from ..secrets.manager import SecretsManager


@dataclass
class VectorStoreConfig:
    name: str
    backend: str
    frame: str
    text_column: str
    id_column: str
    embedding_model: str
    options: Dict[str, str]


class EmbeddingClient:
    def __init__(self, secrets: Optional[SecretsManager] = None) -> None:
        self.registry = EmbeddingProviderRegistry(secrets=secrets)

    def embed(self, model_name: str, texts: List[str]) -> List[List[float]]:
        # EmbeddingProviderRegistry handles provider/model resolution internally.
        return self.registry.get_default_provider().embed_batch(texts, model=model_name)  # type: ignore[arg-type]


class VectorBackend:
    def index(self, cfg: VectorStoreConfig, ids: List[str], embeddings: List[List[float]]) -> None:
        raise NotImplementedError

    def query(self, cfg: VectorStoreConfig, embedding: List[float], top_k: int) -> List[Dict]:
        raise NotImplementedError


class InMemoryVectorBackend(VectorBackend):
    def __init__(self) -> None:
        # store name -> list of tuples(id, embedding, metadata)
        self._store: Dict[str, List[tuple[str, List[float], Dict]]] = {}

    def index(self, cfg: VectorStoreConfig, ids: List[str], embeddings: List[List[float]]) -> None:
        if len(ids) != len(embeddings):
            raise Namel3ssError("Mismatched ids and embeddings length during index")
        bucket = self._store.setdefault(cfg.name, [])
        for id_, emb in zip(ids, embeddings):
            bucket.append((str(id_), emb, {}))

    def query(self, cfg: VectorStoreConfig, embedding: List[float], top_k: int) -> List[Dict]:
        bucket = self._store.get(cfg.name, [])
        if not bucket:
            return []
        results = []
        for id_, emb, meta in bucket:
            score = self._cosine_similarity(embedding, emb)
            results.append({"id": id_, "score": score, "metadata": meta})
        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:top_k]

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        if not a or not b:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


class VectorStoreRegistry:
    def __init__(self, program: IRProgram, secrets: Optional[SecretsManager] = None) -> None:
        self.configs: Dict[str, VectorStoreConfig] = {}
        for name, cfg in getattr(program, "vector_stores", {}).items():
            self.configs[name] = VectorStoreConfig(
                name=cfg.name,
                backend=cfg.backend,
                frame=cfg.frame,
                text_column=cfg.text_column,
                id_column=cfg.id_column,
                embedding_model=cfg.embedding_model,
                options=cfg.options,
            )
        self.backends: Dict[str, VectorBackend] = {"memory": InMemoryVectorBackend(), "default_vector": InMemoryVectorBackend()}
        self.secrets = secrets or SecretsManager()
        self.embedding_client = EmbeddingClient(secrets=self.secrets)

    def get(self, name: str) -> VectorStoreConfig:
        if name not in self.configs:
            raise Namel3ssError(f"N3F-910: Vector store '{name}' is not configured")
        return self.configs[name]

    def backend_for(self, cfg: VectorStoreConfig) -> VectorBackend:
        backend = cfg.backend or "memory"
        if backend not in self.backends:
            raise Namel3ssError(
                f"N3F-910: Vector store '{cfg.name}' is not configured correctly (backend '{backend}' unavailable)."
            )
        return self.backends[backend]

    def index_texts(self, store_name: str, ids: List[str], texts: List[str]) -> None:
        if not texts or not ids:
            return
        cfg = self.get(store_name)
        embeddings = self.embedding_client.embed(cfg.embedding_model, texts)
        backend = self.backend_for(cfg)
        backend.index(cfg, ids, embeddings)

    def query(self, store_name: str, query_text: str, top_k: int = 5, frames=None) -> List[Dict]:
        cfg = self.get(store_name)
        embedding = self.embedding_client.embed(cfg.embedding_model, [query_text])[0]
        backend = self.backend_for(cfg)
        results = backend.query(cfg, embedding, top_k)
        if frames is not None:
            enriched: list[Dict] = []
            for res in results:
                text_val = res.get("text")
                if text_val is None:
                    lookup_id = res.get("id")
                    candidates = [lookup_id]
                    try:
                        if isinstance(lookup_id, str) and lookup_id.isdigit():
                            candidates.append(int(lookup_id))
                    except Exception:
                        pass
                    for cand in candidates:
                        try:
                            rows = frames.query(cfg.frame, {cfg.id_column: cand})
                            if rows and isinstance(rows, list) and isinstance(rows[0], dict):
                                text_val = rows[0].get(cfg.text_column)
                                break
                        except Exception:
                            continue
                enriched.append({**res, "text": text_val})
            return enriched
        return results
