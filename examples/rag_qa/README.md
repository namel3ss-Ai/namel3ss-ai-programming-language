# RAG Q&A Example

An English-first RAG pipeline over a tiny documents frame. It rewrites the question, retrieves context from a vector_store, and answers with an AI.

## Pipeline shape
```ai
frame is "documents": ...
vector_store is "kb": ...

rag pipeline is "kb_qa":
  use vector_store "kb"
  stage is "rewrite":    type is "ai_rewrite"; ai is "rewrite_question"
  stage is "retrieve":   type is "vector_retrieve"; top_k is 3
  stage is "answer":     type is "ai_answer"; ai is "compose_answer"
```
Flows:
- `ingest_documents` seeds two rows and runs `vector_index_frame`.
- `ask` calls a single `rag_query` step against `kb_qa`.

## Run with the CLI
```bash
# seed data + index
n3 flow run ingest_documents --example rag_qa

# ask a question (requires OPENAI_API_KEY or compatible provider)
n3 flow run ask --example rag_qa --set question="What is Namel3ss?"
```

## Load in Studio
Open:
```
http://localhost:8000/studio?example=rag_qa
```
Trace links from CLI runs let you inspect rewrite/retrieve/answer stages end to end.

Looking for multi-query fusion, decomposition, or routing? Check `examples/rag_advanced` for pipelines that exercise the R3 stage palette.
