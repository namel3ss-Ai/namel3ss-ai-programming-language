# RAG Search Example

Shows file uploads to a `docs` index and querying via a flow.

Commands:
```
n3 parse examples/rag_search/app.ai
n3 serve --dry-run
curl -X POST -H "X-API-Key: dev-key" -F "file=@README.md" -F "index=docs" http://localhost:8000/api/rag/upload
curl -X POST -H "X-API-Key: dev-key" -H "Content-Type: application/json" -d '{"code": "", "query": "what is namel3ss?", "indexes": ["docs"]}' http://localhost:8000/api/rag/query
```
