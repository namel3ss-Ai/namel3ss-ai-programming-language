# Phase R1 — Frames & Vector Stores 2.0

- **Frames** now use a single English surface. Declare `frame is "name":` with a `source:` block that either loads from a file or points at a backend table.
  - File example:
    ```ai
    frame is "documents":
      source:
        from file "documents.csv"
        has headers
        delimiter is ","
      select:
        columns are ["id", "title", "content"]
      where:
        row.content is not null
    ```
  - Backend example:
    ```ai
    frame is "orders":
      source:
        backend is "postgres"
        url is env.DATABASE_URL
        table is "orders"
    ```

- **Vector stores** declare retrieval-ready indexes over a frame:
  ```ai
  vector_store is "kb":
    backend is "memory"      # or pgvector/faiss
    frame is "documents"
    text_column is "content"
    id_column is "id"
    embedding_model is "default_embedding"
    metadata_columns are ["title", "category"]
  ```
  Validation now checks required fields, supported backends, column names on the frame, and that the embedding model is actually an embedding model.

- **Vector steps** use clear English fields:
  - Indexing: 
    ```ai
    step is "index_kb":
      kind is "vector_index_frame"
      vector_store is "kb"
      where:
        row.category is "faq"
    ```
  - Querying:
    ```ai
    step is "retrieve":
      kind is "vector_query"
      vector_store is "kb"
      query_text is state.question
      top_k is 5
    ```
  Errors for missing `vector_store`, unknown stores, missing `query_text`, or invalid `top_k` now use friendly N3L-930/931/941 diagnostics.

- **Empty stores** are safe to query: `vector_query` returns an empty `matches` list and empty `context` instead of raising.

These primitives are the foundation for future RAG pipelines. Examples have been refreshed to avoid legacy syntax and to keep the DSL strictly English-first (no `{}` blocks).

# Phase R2 — Declarative RAG Pipelines

- **RAG pipelines** are reusable, English-first retrieval graphs:
  ```ai
  rag pipeline is "support_kb":
    use vector_store "kb"
    stage is "rewrite":
      type is "ai_rewrite"
      ai is "rewrite_ai"
    stage is "retrieve":
      type is "vector_retrieve"
      top_k is 8
    stage is "answer":
      type is "ai_answer"
      ai is "qa_ai"
  ```
  Supported stage types: `ai_rewrite`, `vector_retrieve` (with optional `where:` and `top_k`), `ai_rerank` (optional `top_k`), `context_compress` (optional `max_tokens`), and `ai_answer`. Pipelines enforce unique names and stage validation up front.

- **RAG steps** call a pipeline in one line:
  ```ai
  step is "answer":
    kind is "rag_query"
    pipeline is "support_kb"
    question is state.question
  ```
  Missing `pipeline`, unknown pipeline names, or non-string `question` values return clear, actionable errors.

- **Mini example** tying it together:
  ```ai
  frame is "documents":
    source:
      backend is "memory"
      table is "documents"

  vector_store is "kb":
    backend is "memory"
    frame is "documents"
    text_column is "content"
    id_column is "id"
    embedding_model is "default_embedding"

  rag pipeline is "kb_qa":
    use vector_store "kb"
    stage is "retrieve":
      type is "vector_retrieve"
      top_k is 5
    stage is "answer":
      type is "ai_answer"
      ai is "qa_ai"

  flow is "ask":
    step is "answer":
      kind is "rag_query"
      pipeline is "kb_qa"
      question is state.question
  ```
  Ingest data with `vector_index_frame`, then reuse `rag_query` anywhere you need retrieval-augmented answers.

# Phase R3 — Query Intelligence & Routing

- **New stage types** bring smarter retrieval without changing flow code:
  - `multi_query` expands a question into several rewrites (optional `max_queries`, default 4).
  - `query_decompose` generates subquestions (optional `max_subquestions`, default 3).
  - `query_route` chooses one or more vector stores using an AI router with `choices are ["..."]`.
  - `fusion` merges matches from prior retrieval stages (supports `method is "rrf"` and `top_k`).
- **Multi-query + fusion** example:
  ```ai
  rag pipeline is "fusion_kb":
    use vector_store "kb"
    stage is "expand":
      type is "multi_query"
      ai is "rewrite_ai"
    stage is "retrieve":
      type is "vector_retrieve"
      top_k is 6
    stage is "fusion":
      type is "fusion"
      from stages are ["retrieve"]
    stage is "answer":
      type is "ai_answer"
      ai is "qa_ai"
  ```
- **Decomposition** example:
  ```ai
  rag pipeline is "decompose_kb":
    use vector_store "kb"
    stage is "decompose":
      type is "query_decompose"
      ai is "decomposer_ai"
    stage is "retrieve":
      type is "vector_retrieve"
      top_k is 4
    stage is "answer":
      type is "ai_answer"
      ai is "qa_ai"
  ```
- **Routing** example (chooses between multiple stores, then retrieves):
  ```ai
  rag pipeline is "router_kb":
    use vector_store "kb_default"
    stage is "route":
      type is "query_route"
      ai is "router_ai"
      choices are ["kb_default", "kb_billing", "kb_dev"]
    stage is "retrieve":
      type is "vector_retrieve"
      top_k is 8
    stage is "answer":
      type is "ai_answer"
      ai is "qa_ai"
  ```
- `rag_query` works the same: pass `pipeline is "..."` and `question is ...`, and the pipeline handles expansion, routing, fusion, and answering.
