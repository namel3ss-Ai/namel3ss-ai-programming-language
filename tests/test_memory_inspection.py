from namel3ss.memory.inspection import inspect_memory_state
from namel3ss.runtime.context import clear_recall_snapshot, record_recall_snapshot


def test_inspect_memory_state_returns_snapshot():
    session_id = "sess-inspect"
    ai_id = "ai-demo"
    record_recall_snapshot(ai_id, session_id, rules=[], messages=[{"role": "user", "content": "hello"}])
    snapshot = inspect_memory_state(session_id, ai_id=ai_id)
    assert ai_id in snapshot.get("recall_snapshots", {})
    clear_recall_snapshot(ai_id, session_id)


def test_inspect_memory_state_handles_missing_session():
    snapshot = inspect_memory_state("missing-session", ai_id="unknown")
    assert snapshot.get("recall_snapshots", {}).get("unknown") is None
