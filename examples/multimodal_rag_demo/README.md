# Multimodal RAG Demo

This demo shows how to combine table-aware retrieval with basic multimodal hooks.

What it does:
- Declares a `frame` with a `table:` block describing primary key, display columns, and multimodal columns.
- Runs a RAG pipeline with:
  - `table_lookup` to pull matching rows,
  - `table_summarise` to turn rows into readable snippets,
  - `multimodal_embed` to embed paired image/text columns into a vector store,
  - `vector_retrieve` and `ai_answer` to compose the final answer.

Run it:
```bash
n3 run examples/multimodal_rag_demo/multimodal_rag.ai --flow product_query --set state.question="Tell me about CameraX"
```
