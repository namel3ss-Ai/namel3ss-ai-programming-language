# RAG App Template

Contents:
- `app.ai`: file upload component to index docs into a `docs` index, plus a flow that rewrites and queries.

Usage:
```
n3 parse app.ai
n3 serve --dry-run
# upload via /api/rag/upload then query with /api/rag/query
```
