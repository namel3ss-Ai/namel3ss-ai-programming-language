# 7. RAG, Memory, and Data

## Memory
```ai
memory "support_history":
  type "conversation"
```
Use memory in agents/flows to keep context. Some advanced patterns may be experimental—check lint/diagnostics for guidance.

## Frames & data
Frames behave like list-like tables:
```ai
frame "sales_data":
  from file "sales.csv"
  has headers
  select region, revenue
  where revenue is greater than 0
```

## RAG basics
- Configure models and retrieval flows (`rewrite`, `lookup`, `compose`).
- Use frames or custom retrieval logic; keep examples lightweight to avoid heavy dependencies.

## Exercises
1. Define a conversation memory and reference it in an agent goal.
2. Create a frame over a CSV file and slice/filter it.
3. Sketch a three-step RAG flow: rewrite → lookup → answer.
