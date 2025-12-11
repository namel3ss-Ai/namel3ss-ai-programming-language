# Chapter 8 — Data & RAG: Frames and Vector Stores

- **Frames:** Tables with backend and table name.
- **Vector stores:** Point at frames with `text_column`, `id_column`, and embedding model/provider.
- **Indexing:** `vector_index_frame` step.
- **Query:** `vector_query` step returning matches for downstream AI.
- **Graphs:** `graph is "name": from frame is "..."; id_column/text_column plus entities/relations config; optional storage nodes/edges frames.`
- **Graph summaries:** `graph_summary is "name": graph is "..."; method/model; max_nodes_per_summary` for clustered text snippets.
- **Graph-aware RAG:** Pipeline stages `graph_query` (graph, optional `max_hops`/`max_nodes`/`strategy`) and `graph_summary_lookup` (graph_summary, optional `top_k`) sit next to `vector_retrieve` and `ai_answer`.

Example (ingest + answer):
```ai
frame is "docs":
  source:
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

Graph-aware pipeline sketch:
```ai
graph is "support_graph":
  from frame is "docs"
  id_column is "id"
  text_column is "content"
  entities:
    model is "gpt-4o-mini"

graph_summary is "support_graph_summary":
  graph is "support_graph"
  method is "community"
  max_nodes_per_summary is 20

rag pipeline is "graph_qa":
  use vector_store "kb"
  stage is "graph_stage":
    type is "graph_query"
    graph is "support_graph"
    max_hops is 2
  stage is "summaries":
    type is "graph_summary_lookup"
    graph_summary is "support_graph_summary"
    top_k is 3
  stage is "retrieve":
    type is "vector_retrieve"
    top_k is 4
  stage is "answer":
    type is "ai_answer"
    ai is "qa_ai"

flow is "ask":
  step is "answer":
    kind is "rag_query"
    pipeline is "graph_qa"
    question is state.question

# Table-aware and multimodal hooks

Add table metadata to frames and mix table/multimodal stages into a pipeline:

```ai
frame is "products":
  source:
    backend is "memory"
    table is "products"
  table:
    primary_key is "product_id"
    display_columns are ["name", "category"]
    text_column is "description"
    image_column is "image_url"

rag pipeline is "product_rag":
  use vector_store "kb"
  stage is "lookup":
    type is "table_lookup"
    frame is "products"
    match_column is "name"
  stage is "summaries":
    type is "table_summarise"
    frame is "products"
    group_by is "category"
  stage is "images":
    type is "multimodal_embed"
    frame is "products"
    image_column is "image_url"
    text_column is "description"
    output_vector_store is "kb"
  stage is "answer":
    type is "ai_answer"
    ai is "qa_ai"
```
```

Cross-reference: parser data/vector/graph rules `src/namel3ss/parser.py`; runtime RAG in `src/namel3ss/runtime/vectorstores.py`, `src/namel3ss/rag/*`; tests `tests/test_vector_store_parse.py`, `tests/test_vector_index_frame.py`, `tests/test_vector_query_runtime.py`, `tests/test_vector_runtime.py`, `tests/test_parser_rag_graph.py`, `tests/test_rag_graph_runtime.py`; examples `examples/rag_qa/rag_qa.ai`, `examples/graph_rag_demo/graph_rag.ai`.
