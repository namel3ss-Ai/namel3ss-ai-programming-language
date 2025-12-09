from __future__ import annotations

from typing import Any, Dict, Optional

from .engine import MemoryEngine
from ..runtime.context import get_last_recall_snapshot, list_recall_snapshots


def inspect_memory_state(
    session_id: str,
    ai_id: str | None = None,
    memory_engine: MemoryEngine | None = None,
    memory_name: str | None = None,
) -> Dict[str, Any]:
    """
    Build a lightweight view of memory for a session.
    """

    if ai_id:
        snapshots = {ai_id: get_last_recall_snapshot(ai_id, session_id)}
    else:
        snapshots = list_recall_snapshots(session_id)
    result: Dict[str, Any] = {
        "session_id": session_id,
        "ai_id": ai_id,
        "recall_snapshots": snapshots,
    }
    if memory_engine and memory_name:
        try:
            result["conversation"] = memory_engine.load_conversation(memory_name, session_id=session_id)
        except Exception as exc:  # pragma: no cover - defensive
            result["conversation_error"] = str(exc)
    return result
