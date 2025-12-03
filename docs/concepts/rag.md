# RAG

RAG V3 supports multi-index and hybrid retrieval (dense + sparse), cross-store queries (indexes + memory), rewriting, and reranking (deterministic + OpenAI). Vector stores include in-memory and optional pgvector.

Endpoints: `/api/rag/query`, `/api/rag/upload`. Studio provides a RAG query panel and memory summary. Metrics and traces capture retrievals, token/cost, and rerankers.
