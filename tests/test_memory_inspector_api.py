import json
from pathlib import Path

from fastapi.testclient import TestClient

from namel3ss.memory.conversation import SqliteConversationMemoryBackend
from namel3ss.runtime.context import record_recall_snapshot
from namel3ss.server import create_app


PROGRAM = (
    'model "default":\n'
    '  provider "openai:gpt-4.1-mini"\n'
    'ai "support_bot":\n'
    '  model "default"\n'
    "  memory:\n"
    "    kinds:\n"
    "      short_term:\n"
    "        window is 5\n"
    '      long_term:\n'
    '        store is "chat_long"\n'
    '      profile:\n'
    '        store is "user_profile"\n'
    "    recall:\n"
    '      - source is "short_term"\n'
    "        count is 5\n"
    '      - source is "long_term"\n'
    "        top_k is 2\n"
    '      - source is "profile"\n'
    "        include is true\n"
)


def _setup_project(tmp_path: Path, monkeypatch) -> dict[str, SqliteConversationMemoryBackend]:
    project_file = tmp_path / "support.ai"
    project_file.write_text(PROGRAM, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    short_db = tmp_path / "short.db"
    long_db = tmp_path / "long.db"
    profile_db = tmp_path / "profile.db"
    monkeypatch.setenv(
        "N3_MEMORY_STORES_JSON",
        json.dumps(
            {
                "default_memory": {"kind": "sqlite", "url": f"sqlite:///{short_db}"},
                "chat_long": {"kind": "sqlite", "url": f"sqlite:///{long_db}"},
                "user_profile": {"kind": "sqlite", "url": f"sqlite:///{profile_db}"},
            }
        ),
    )
    stores = {
        "default_memory": SqliteConversationMemoryBackend(url=f"sqlite:///{short_db}"),
        "chat_long": SqliteConversationMemoryBackend(url=f"sqlite:///{long_db}"),
        "user_profile": SqliteConversationMemoryBackend(url=f"sqlite:///{profile_db}"),
    }
    return stores


def _populate_memory(stores: dict[str, SqliteConversationMemoryBackend]) -> None:
    short_backend = stores["default_memory"]
    short_backend.append_turns(
        "support_bot",
        "sess_a",
        [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ],
        user_id="user-123",
    )
    short_backend.append_turns(
        "support_bot",
        "sess_b",
        [
            {"role": "user", "content": "Need help"},
            {"role": "assistant", "content": "Sure"},
        ],
        user_id="user-456",
    )
    stores["chat_long"].append_summary("support_bot::long_term", "user:user-123", "User asked about billing yesterday.")
    stores["user_profile"].append_facts("support_bot::profile", "user:user-123", ["User lives in Kampala."])
    record_recall_snapshot(
        "support_bot",
        "sess_a",
        [{"source": "short_term", "count": 5}],
        [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"},
        ],
    )


def _client(tmp_path: Path, monkeypatch) -> tuple[TestClient, dict[str, SqliteConversationMemoryBackend]]:
    stores = _setup_project(tmp_path, monkeypatch)
    _populate_memory(stores)
    client = TestClient(create_app())
    return client, stores


def test_memory_sessions_endpoint_lists_sessions(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    response = client.get("/api/memory/ai/support_bot/sessions", headers={"X-API-Key": "dev-key"})
    assert response.status_code == 200
    body = response.json()
    assert body["ai"] == "support_bot"
    session_ids = [s["id"] for s in body["sessions"]]
    assert "sess_a" in session_ids
    assert any(s["turns"] == 2 for s in body["sessions"])
    assert any(s.get("user_id") == "user-123" for s in body["sessions"])


def test_memory_session_detail_returns_combined_view(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    response = client.get(
        "/api/memory/ai/support_bot/sessions/sess_a",
        headers={"X-API-Key": "dev-key"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == "user-123"
    assert body["short_term"]["turns"][0]["content"] == "Hello"
    assert body["long_term"]["items"][0]["summary"] == "User asked about billing yesterday."
    assert "User lives in Kampala." in body["profile"]["facts"]
    assert body["last_recall_snapshot"]["messages"][1]["content"] == "Hello"
    assert body["policies"]["long_term"]["scope"] == "per_user"
    assert body["policies"]["profile"]["scope"] == "per_user"


def test_memory_clear_endpoint_wipes_requested_kinds(tmp_path, monkeypatch):
    client, stores = _client(tmp_path, monkeypatch)
    response = client.post(
        "/api/memory/ai/support_bot/sessions/sess_a/clear",
        json={"kinds": ["short_term", "profile"]},
        headers={"X-API-Key": "dev-key"},
    )
    assert response.status_code == 200
    assert stores["default_memory"].get_full_history("support_bot", "sess_a") == []
    assert stores["user_profile"].get_facts("support_bot::profile", "user:user-123") == []
