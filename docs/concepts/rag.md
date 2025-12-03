# RAG

RAG V3 supports multi-index and hybrid retrieval (dense + sparse), cross-store queries (indexes + memory), rewriting, and reranking (deterministic + OpenAI). Vector stores include in-memory and optional pgvector.

Embedding providers (pluggable):
- `deterministic` (default for CI)
- `openai` (uses `OPENAI_API_KEY`/`N3_OPENAI_API_KEY`, `N3_EMBEDDINGS_MODEL`)
- `http_json` (generic POST; configure `N3_EMBEDDINGS_BASE_URL`, `N3_EMBEDDINGS_RESPONSE_PATH`, optional model)

Env keys:
- `N3_EMBEDDINGS_PROVIDER` (deterministic|openai|http_json)
- `N3_EMBEDDINGS_MODEL`
- `N3_EMBEDDINGS_BASE_URL`
- `N3_EMBEDDINGS_RESPONSE_PATH`

Vector stores:
- In-memory (default): good for dev/tests.
- PgVector: persistent Postgres-based vectors (`N3_RAG_INDEX_<NAME>_BACKEND=pgvector`, `N3_RAG_PGVECTOR_DSN`, optional `N3_RAG_INDEX_<NAME>_PG_TABLE`).
- FAISS: local high-performance search (`N3_RAG_INDEX_<NAME>_BACKEND=faiss`, provide dimension via index options; dependency optional).

Endpoints: `/api/rag/query`, `/api/rag/upload`. Studio provides a RAG query panel and memory summary. Metrics and traces capture retrievals, token/cost, and rerankers.
