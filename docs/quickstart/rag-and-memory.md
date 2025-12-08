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
4. Studio: open the Memory panel to inspect short-term turns, long-term summaries, and profile facts for each AI/session.

The RAG example defines default indexes and uses the in-memory vector store for CI-friendly runs.

Backend selection:
- Default is in-memory.
- PgVector: set `N3_RAG_INDEX_docs_BACKEND=pgvector` and `N3_RAG_PGVECTOR_DSN`.
- FAISS: set `N3_RAG_INDEX_docs_BACKEND=faiss` and ensure FAISS is installed; provide index dimension via index options or defaults.

## Studio Memory Inspector

Studio’s **Memory** panel shows everything currently stored for an AI/session:

- **Sessions list** sourced from the short-term backend with last activity + turn count.
- **Conversation** transcript exactly as the runtime stored it (short_term window).
- **Long-Term Memory** summaries/snippets and **Profile Facts** produced by pipelines.
- **Last Recall Snapshot** — the recall rules plus the exact messages that were sent to the model.

Use the _Clear All_ / _Clear Long-Term_ buttons to wipe specific kinds for a test session. These actions call
`POST /api/memory/ai/{ai_id}/sessions/{session_id}/clear` and are intended for development/debugging only;
production deployments should manage retention via backend settings instead of clearing through Studio.

Memory data is also available directly via HTTP:

- `GET /api/memory/ai/{ai_id}/sessions` — list recent sessions for an AI.
- `GET /api/memory/ai/{ai_id}/sessions/{session_id}` — return short_term, long_term, profile, and the last recall snapshot.
- `POST /api/memory/ai/{ai_id}/sessions/{session_id}/clear` — clear specific kinds (short_term, long_term, profile) for that session.
