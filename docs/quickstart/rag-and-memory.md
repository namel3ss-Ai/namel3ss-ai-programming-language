# RAG & Memory

Use the `examples/rag_search/app.ai` program.

Steps:
1. Start the server: `python -m namel3ss.server`
2. Upload a document:
   ```
   curl -X POST -H "X-API-Key: dev-key" -F "file=@README.md" -F "index=docs" http://localhost:8000/api/rag/upload
   ```
3. Query it:
   ```
   curl -X POST -H "X-API-Key: dev-key" -H "Content-Type: application/json" \ 
     -d '{"code": "", "query": "what is namel3ss?", "indexes": ["docs"]}' \
     http://localhost:8000/api/rag/query
   ```
4. Studio: use the RAG panel and Memory summary to view indexed items.

The RAG example defines default indexes and uses the in-memory vector store for CI-friendly runs.

Backend selection:
- Default is in-memory.
- PgVector: set `N3_RAG_INDEX_docs_BACKEND=pgvector` and `N3_RAG_PGVECTOR_DSN`.
- FAISS: set `N3_RAG_INDEX_docs_BACKEND=faiss` and ensure FAISS is installed; provide index dimension via index options or defaults.
