import json
from pathlib import Path

from namel3ss.cli import main
from namel3ss.memory.conversation import SqliteConversationMemoryBackend
from namel3ss.runtime.context import record_recall_snapshot

PROGRAM = (
    'model is "default":\n'
    '  provider is "openai:gpt-4.1-mini"\n'
    'ai is "support_bot":\n'
    '  model is "default"\n'
    "  memory:\n"
    "    kinds:\n"
    "      short_term:\n"
    "        window is 4\n"
    '      long_term:\n'
    '        store is "chat_long"\n'
    '      profile:\n'
    '        store is "user_profile"\n'
    "    recall:\n"
    '      - source is "short_term"\n'
    "        count is 4\n"
    '      - source is "long_term"\n'
    "        top_k is 2\n"
    '      - source is "profile"\n'
    "        include is true\n"
)


def _write_program(tmp_path: Path) -> Path:
    program_file = tmp_path / "memory_demo.ai"
    program_file.write_text(PROGRAM, encoding="utf-8")
    return program_file


def _configure_memory(tmp_path: Path, monkeypatch):
    short_db = tmp_path / "short_cli.db"
    long_db = tmp_path / "long_cli.db"
    profile_db = tmp_path / "profile_cli.db"
    monkeypatch.setenv("N3_OPENAI_API_KEY", "test-key")
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
    short_backend = SqliteConversationMemoryBackend(url=f"sqlite:///{short_db}")
    long_backend = SqliteConversationMemoryBackend(url=f"sqlite:///{long_db}")
    profile_backend = SqliteConversationMemoryBackend(url=f"sqlite:///{profile_db}")
    short_backend.append_turns(
        "support_bot",
        "sess_cli",
        [
            {"role": "user", "content": "Hi inspector"},
            {"role": "assistant", "content": "Hello!"},  # keep ascii
        ],
        user_id="user-cli",
    )
    long_backend.append_summary("support_bot::long_term", "user:user-cli", "Billing summary entry.")
    profile_backend.append_facts("support_bot::profile", "user:user-cli", ["Prefers SMS follow-up."])
    record_recall_snapshot(
        "support_bot",
        "sess_cli",
        [{"source": "short_term", "count": 4}],
        [{"role": "system", "content": "debug context"}],
        diagnostics=[{"kind": "short_term", "selected": 2}],
    )


def test_cli_memory_inspect_plan_only(tmp_path, monkeypatch, capsys):
    program_file = _write_program(tmp_path)
    _configure_memory(tmp_path, monkeypatch)
    main(
        [
            "memory-inspect",
            "--file",
            str(program_file),
            "--ai",
            "support_bot",
            "--plan-only",
        ]
    )
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output["ai"] == "support_bot"
    assert any(kind["kind"] == "short_term" for kind in output["plan"]["kinds"])
    assert output["state"] is None


def test_cli_memory_inspect_with_session_state(tmp_path, monkeypatch, capsys):
    program_file = _write_program(tmp_path)
    _configure_memory(tmp_path, monkeypatch)
    main(
        [
            "memory-inspect",
            "--file",
            str(program_file),
            "--ai",
            "support_bot",
            "--session-id",
            "sess_cli",
        ]
    )
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output["state"]["session_id"] == "sess_cli"
    assert output["state"]["kinds"]["short_term"]["turns"][0]["content"] == "Hi inspector"
    assert output["state"]["kinds"]["long_term"]["items"][0]["summary"] == "Billing summary entry."
    assert output["state"]["recall_snapshot"]["diagnostics"][0]["kind"] == "short_term"
