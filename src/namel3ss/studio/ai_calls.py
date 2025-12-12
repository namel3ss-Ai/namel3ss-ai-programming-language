"""
Helpers to expose AI call context snapshots for Studio.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .. import ir
from ..memory.inspection import describe_memory_state
from ..runtime import context as runtime_context


def describe_ai_call_context(
    program: Any,
    ai_id: str,
    session_id: str,
    engine: Any,
) -> Dict[str, Any]:
    """
    Return a structured view of the most recent AI call snapshot for the requested
    ai/session. Falls back to empty payloads when unavailable.
    """

    ai_calls = getattr(program, "ai_calls", {}) or {}
    ai_call: Optional[ir.IRAiCall] = ai_calls.get(ai_id)
    if ai_call is None:
        raise KeyError(f"ai '{ai_id}' not found")

    snapshot = runtime_context.get_last_recall_snapshot(ai_id, session_id) or {}
    messages = snapshot.get("messages") or []
    diagnostics = snapshot.get("diagnostics") or []
    rules = snapshot.get("rules") or []

    memory_state = describe_memory_state(engine, ai_call, session_id=session_id, limit=50)
    rag_matches = []
    for msg in messages:
        if msg.get("kind") == "vector_context" and isinstance(msg.get("content"), str):
            rag_matches.append({"text": msg.get("content"), "source": msg.get("source"), "score": msg.get("score")})

    model = getattr(ai_call, "model", None) or getattr(ai_call, "provider_model", None) or ""
    return {
        "ai_id": ai_id,
        "session_id": session_id,
        "model": model,
        "rag_pipeline": getattr(ai_call, "rag_pipeline", None) or getattr(ai_call, "rag", None),
        "timestamp": snapshot.get("timestamp"),
        "messages": messages,
        "recall_rules": rules,
        "recall_diagnostics": diagnostics,
        "memory": memory_state,
        "rag": {"matches": rag_matches},
    }
