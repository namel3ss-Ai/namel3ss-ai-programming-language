# Graph RAG Demo

This example builds a tiny knowledge graph from three support notes, precomputes graph summaries, and wires a RAG pipeline that blends graph hops, graph summaries, and vector search.

What it demonstrates:
- `graph is` declarations that extract entities/relations from a frame.
- `graph_summary is` declarations to precompute community-style summaries.
- RAG stages `graph_query` and `graph_summary_lookup` sitting alongside `vector_retrieve` and `ai_answer`.
- A single `rag_query` step that fans into graph + vector retrieval before answering.

How to run:
```bash
n3 run examples/graph_rag_demo/graph_rag.ai --flow graph_rag_demo --set state.question="Who maintains ComponentB and what service does it integrate with?"
```

Relevant files:
- `graph_rag.ai` — models, frames, graph + summary, pipeline, and flow.
- `data/support_notes.csv` — the small source frame the graph is built from.
