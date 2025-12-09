# Chapter 8 — Data & RAG: Frames and Vector Stores

- **Frames:** Tables with backend and table name.
- **Vector stores:** Point at frames with `text_column`, `id_column`, and embedding model/provider.
- **Indexing:** `vector_index_frame` step.
- **Query:** `vector_query` step returning matches for downstream AI.

Example (ingest + answer):
```ai
frame is "docs":
  backend is "memory"
  table is "docs"

vector_store is "kb":
  backend is "memory"
  frame is "docs"
  text_column is "content"
  id_column is "id"
  embedding_model is "default_embedding"

flow is "ingest_docs":
  step is "insert":
    kind is "frame_insert"
    frame is "docs"
    values:
      id: "doc-1"
      content: "Refunds take 3-5 business days."
  step is "index":
    kind is "vector_index_frame"
    vector_store is "kb"

flow is "ask":
  step is "retrieve":
    kind is "vector_query"
    vector_store is "kb"
    query_text is state.question
    top_k is 2
  step is "answer":
    kind is "ai"
    target is "qa_ai"
```

Cross-reference: parser data/vector rules `src/namel3ss/parser.py`; runtime RAG in `src/namel3ss/runtime/vectorstores.py`, `src/namel3ss/rag/*`; tests `tests/test_vector_store_parse.py`, `tests/test_vector_index_frame.py`, `tests/test_vector_query_runtime.py`, `tests/test_vector_runtime.py`; example `examples/rag_qa/rag_qa.ai`.
