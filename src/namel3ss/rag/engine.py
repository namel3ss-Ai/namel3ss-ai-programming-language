"""
RAG engine orchestrating multi-index retrieval, hybrid scoring, and reranking.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional
from uuid import uuid4

from .factory import VectorStoreFactory
from .models import RAGItem, ScoredItem
from .index_config import RAGIndexConfig
from .rewriter import DeterministicRewriter, QueryRewriter
from .reranker import DeterministicReranker, Reranker
from .embedding_registry import EmbeddingProviderRegistry
from .store_registry import VectorStoreRegistry
from .vectorstores.memory import InMemoryVectorStore
from ..secrets.manager import SecretsManager
from ..metrics.tracker import MetricsTracker
from ..obs.tracer import Tracer
from ..memory.engine import MemoryEngine


class RAGEngine:
    def __init__(
        self,
        indexes: Optional[List[RAGIndexConfig]] = None,
        secrets: Optional[SecretsManager] = None,
        metrics: Optional[MetricsTracker] = None,
        tracer: Optional[Tracer] = None,
        memory_engine: Optional[MemoryEngine] = None,
        embedding_provider=None,
    ) -> None:
        self.secrets = secrets or SecretsManager()
        self.metrics = metrics
        self.tracer = tracer
        self.memory_engine = memory_engine
        self.index_registry: Dict[str, RAGIndexConfig] = {}
        default_indexes = indexes or [RAGIndexConfig(name="default", backend="memory", collection="default")]
        self._default_index = default_indexes[0].name
        for idx in default_indexes:
            self.index_registry[idx.name] = idx
        self.store_registry = VectorStoreRegistry(self.secrets)
        self.factory = VectorStoreFactory(self.secrets)
        self.store = self._get_store(self.index_registry[self._default_index])
        registry = EmbeddingProviderRegistry(self.secrets)
        self.embedding_provider = embedding_provider or registry.get_default_provider()

    def _get_store(self, index: RAGIndexConfig):
        return self.store_registry.get_store(index)

    def index_documents(self, index_name: str, texts: List[str]) -> None:
        if index_name not in self.index_registry:
            self.index_registry[index_name] = RAGIndexConfig(name=index_name, backend="memory", collection=index_name)
        index = self.index_registry[index_name]
        store = self._get_store(index)
        embeddings = self.embedding_provider.embed_batch(texts)
        items = [
            RAGItem(
                id=str(uuid4()),
                text=text,
                metadata={"index": index_name},
                embedding=embeddings[idx],
                source=index_name,
            )
            for idx, text in enumerate(texts)
        ]
        if hasattr(store, "add_sync"):
            store.add_sync(items)  # type: ignore[attr-defined]
        else:
            import asyncio
            self._run_coro_blocking(store.a_add(items))

    async def a_index_documents(self, index_name: str, texts: List[str]) -> None:
        if index_name not in self.index_registry:
            self.index_registry[index_name] = RAGIndexConfig(name=index_name, backend="memory", collection=index_name)
        index = self.index_registry[index_name]
        store = self._get_store(index)
        embeddings = self.embedding_provider.embed_batch(texts)
        items = [
            RAGItem(
                id=str(uuid4()),
                text=text,
                metadata={"index": index_name},
                embedding=embeddings[idx],
                source=index_name,
            )
            for idx, text in enumerate(texts)
        ]
        await store.a_add(items)

    async def a_retrieve(
        self,
        query: str,
        index_names: Optional[List[str]] = None,
        include_memory: bool = True,
    ) -> List[ScoredItem]:
        selected = index_names or list(self.index_registry.keys())
        if self.tracer:
            self.tracer.record_rag_query(selected, hybrid=None)
        query_text = query
        # Query rewrite
        rewritten = await self._rewrite(query_text)
        query_embedding = self.embedding_provider.embed_text(rewritten)
        candidates: List[ScoredItem] = []
        for name in selected:
            index = self.index_registry.get(name)
            if not index:
                continue
            store = self._get_store(index)
            dense_results = await store.a_query(query_embedding, k=index.k)
            # Sparse scoring (BM25-ish) on items if supported
            if index.enable_hybrid and hasattr(store, "all_items"):
                sparse_results = self._sparse_score(rewritten, store.all_items())
                dense_results = self._merge_hybrid(dense_results, sparse_results, index)
            candidates.extend(dense_results)
        # Cross-store: memory
        if include_memory and self.memory_engine:
            mem_hits = self._memory_search(rewritten)
            candidates.extend(mem_hits)
        # Rerank
        reranked = await self._rerank(rewritten, candidates)
        if self.metrics:
            self.metrics.record_rag_query(backends=selected, hybrid_used=any(self.index_registry[n].enable_hybrid for n in selected if n in self.index_registry))
        return reranked

    def retrieve(self, source: Optional[str], query: str, top_k: int = 5) -> List[ScoredItem]:
        # Backward-compatible synchronous API: use default index or provided source.
        indexes = [source] if source else None
        results = self._run_coro_blocking_return(self.a_retrieve(query, index_names=indexes))
        if self.tracer:
            self.tracer.update_last_rag_result_count(len(results))
        return results[:top_k]

    def _sparse_score(self, query: str, items: List[RAGItem]) -> List[ScoredItem]:
        query_terms = query.lower().split()
        scored: List[ScoredItem] = []
        for item in items:
            text_terms = item.text.lower().split()
            match = sum(text_terms.count(t) for t in query_terms)
            score = match / (len(text_terms) + 1)
            scored.append(ScoredItem(item=item, score=score, source=item.source or "memory"))
        scored.sort(key=lambda x: x.score, reverse=True)
        return scored

    def _merge_hybrid(
        self, dense: List[ScoredItem], sparse: List[ScoredItem], index: RAGIndexConfig
    ) -> List[ScoredItem]:
        combined: Dict[str, ScoredItem] = {}
        for d in dense:
            combined[d.item.id] = ScoredItem(
                item=d.item,
                score=index.dense_weight * d.score,
                source=d.source,
            )
        for s in sparse:
            if s.item.id in combined:
                merged_score = combined[s.item.id].score + index.sparse_weight * s.score
                combined[s.item.id] = ScoredItem(item=s.item, score=merged_score, source=s.source)
            else:
                combined[s.item.id] = ScoredItem(
                    item=s.item, score=index.sparse_weight * s.score, source=s.source
                )
        results = list(combined.values())
        results.sort(key=lambda x: x.score, reverse=True)
        return results

    def _memory_search(self, query: str) -> List[ScoredItem]:
        hits: List[ScoredItem] = []
        if not self.memory_engine:
            return hits
        for space in self.memory_engine.spaces.keys():
            for item in self.memory_engine.get_recent(space, limit=50):
                text = item.content
                if query.lower() in text.lower():
                    hits.append(
                        ScoredItem(
                            item=RAGItem(id=item.id, text=text, metadata=item.metadata, source=f"memory:{space}"),
                            score=1.0,
                            source=f"memory:{space}",
                        )
                    )
        return hits

    async def _rewrite(self, query: str) -> str:
        rewriter: QueryRewriter = DeterministicRewriter()
        return await rewriter.a_rewrite(query, None)

    async def _rerank(self, query: str, candidates: List[ScoredItem]) -> List[ScoredItem]:
        reranker: Reranker = DeterministicReranker()
        return await reranker.a_rerank(query, candidates, None)

    def _run_coro_blocking(self, coro) -> None:
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(coro)
            return
        new_loop = asyncio.new_event_loop()
        new_loop.run_until_complete(coro)
        new_loop.close()

    def _run_coro_blocking_return(self, coro):
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        new_loop = asyncio.new_event_loop()
        result = new_loop.run_until_complete(coro)
        new_loop.close()
        return result
