import json

import pytest

from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.config import N3Config
from namel3ss.errors import IRError, Namel3ssError
from namel3ss.ir import (
    IRAiCall,
    IRAiMemoryConfig,
    IRAiRecallRule,
    IRAiShortTermMemoryConfig,
    ast_to_ir,
)
from namel3ss.memory.conversation import InMemoryConversationMemoryBackend, SqliteConversationMemoryBackend
from namel3ss.memory.registry import build_memory_store_registry
from namel3ss.parser import parse_source
from namel3ss.secrets.manager import SecretsManager
from namel3ss.runtime.context import ExecutionContext, execute_ai_call_with_registry


def test_ai_memory_store_unknown(monkeypatch):
    source = MODEL_BLOCK + (
        'ai is "support_bot":\n'
        '  model is "gpt-4.1-mini"\n'
        "  memory:\n"
        '    kind is "conversation"\n'
        '    store is "tickets_memory"\n'
    )
    monkeypatch.setenv("N3_MEMORY_STORES_JSON", json.dumps({"default_memory": {"kind": "in_memory"}}))
    module = parse_source(source)
    with pytest.raises(IRError) as excinfo:
        ast_to_ir(module)
    assert "N3L-1201" in str(excinfo.value)


def test_ai_memory_store_known(monkeypatch):
    source = MODEL_BLOCK + (
        'ai is "support_bot":\n'
        '  model is "gpt-4.1-mini"\n'
        "  memory:\n"
        '    kind is "conversation"\n'
        '    store is "chat_long"\n'
    )
    stores = {
        "default_memory": {"kind": "in_memory"},
        "chat_long": {"kind": "in_memory"},
    }
    monkeypatch.setenv("N3_MEMORY_STORES_JSON", json.dumps(stores))
    module = parse_source(source)
    program = ast_to_ir(module)
    assert "support_bot" in program.ai_calls


def test_ai_memory_store_defaults_when_not_specified(monkeypatch):
    source = MODEL_BLOCK + (
        'ai is "support_bot":\n'
        '  model is "gpt-4.1-mini"\n'
        "  memory:\n"
        '    kind is "conversation"\n'
        '    window is 20\n'
    )
    stores = {"default_memory": {"kind": "in_memory"}}
    monkeypatch.setenv("N3_MEMORY_STORES_JSON", json.dumps(stores))
    module = parse_source(source)
    program = ast_to_ir(module)
    assert program.ai_calls["support_bot"].memory is not None
    assert program.ai_calls["support_bot"].memory.store is None


def test_ai_memory_store_defaults_without_config(monkeypatch):
    source = MODEL_BLOCK + (
        'ai is "support_bot":\n'
        '  model is "gpt-4.1-mini"\n'
        "  memory:\n"
        '    kind is "conversation"\n'
        '    window is 20\n'
    )
    monkeypatch.delenv("N3_MEMORY_STORES_JSON", raising=False)
    module = parse_source(source)
    program = ast_to_ir(module)
    assert program.ai_calls["support_bot"].memory is not None
    assert program.ai_calls["support_bot"].memory.store is None


def test_memory_store_registry_builds_defaults(monkeypatch):
    monkeypatch.delenv("N3_MEMORY_STORES_JSON", raising=False)
    cfg = N3Config(memory_stores={})
    secrets = SecretsManager()
    registry = build_memory_store_registry(secrets, cfg)
    assert "default_memory" in registry


def test_memory_store_registry_custom_store(monkeypatch):
    monkeypatch.delenv("N3_MEMORY_STORES_JSON", raising=False)
    cfg = N3Config(memory_stores={"chat_long": {"kind": "in_memory"}})
    secrets = SecretsManager()
    registry = build_memory_store_registry(secrets, cfg)
    assert "chat_long" in registry
    assert "default_memory" in registry


def test_memory_store_registry_builds_sqlite_store(tmp_path, monkeypatch):
    monkeypatch.delenv("N3_MEMORY_STORES_JSON", raising=False)
    db_path = tmp_path / "memory.db"
    cfg = N3Config(
        memory_stores={
            "default_memory": {"kind": "in_memory"},
            "chat_long": {"kind": "sqlite", "url": f"sqlite:///{db_path.as_posix()}"},
        }
    )
    secrets = SecretsManager()
    registry = build_memory_store_registry(secrets, cfg)
    default_backend = registry["default_memory"]
    assert isinstance(default_backend, InMemoryConversationMemoryBackend)
    sqlite_backend = registry["chat_long"]
    assert isinstance(sqlite_backend, SqliteConversationMemoryBackend)
    sqlite_backend.append_turns(
        "support_bot",
        "session-1",
        [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ],
    )
    history = sqlite_backend.load_history("support_bot", "session-1", window=10)
    assert len(history) == 2
    assert history[0]["content"] == "hello"


def test_memory_store_registry_sqlite_requires_url(monkeypatch):
    monkeypatch.delenv("N3_MEMORY_STORES_JSON", raising=False)
    cfg = N3Config(memory_stores={"chat_long": {"kind": "sqlite"}})
    secrets = SecretsManager()
    with pytest.raises(Namel3ssError):
        build_memory_store_registry(secrets, cfg)


class RecordingMemoryBackend:
    def __init__(self) -> None:
        self.history_calls: list[tuple[str, str, int]] = []
        self.append_calls: list[tuple[str, str, list[dict[str, str]], str | None]] = []
        self.summary_calls: list[tuple[str, str, str]] = []
        self.fact_calls: list[tuple[str, str, list[str]]] = []

    def load_history(self, ai_id: str, session_id: str, window: int):
        self.history_calls.append((ai_id, session_id, window))
        return []

    def append_turns(
        self,
        ai_id: str,
        session_id: str,
        turns: list[dict[str, str]],
        user_id: str | None = None,
    ) -> None:
        self.append_calls.append((ai_id, session_id, list(turns), user_id))

    def append_summary(self, ai_id: str, session_id: str, summary: str) -> None:
        self.summary_calls.append((ai_id, session_id, summary))
        self.append_turns(ai_id, session_id, [{"role": "system", "content": summary}])

    def append_facts(self, ai_id: str, session_id: str, facts: list[str]) -> None:
        self.fact_calls.append((ai_id, session_id, list(facts)))
        turns = [{"role": "system", "content": fact} for fact in facts]
        self.append_turns(ai_id, session_id, turns)


def test_ai_call_uses_configured_memory_store(monkeypatch):
    monkeypatch.delenv("N3_MEMORY_STORES_JSON", raising=False)
    backend = RecordingMemoryBackend()
    ctx = ExecutionContext(
        app_name="test",
        request_id="req-1",
        memory_stores={"chat_long": backend},
    )
    ctx.user_input = "hello"
    ai_call = IRAiCall(
        name="support_bot",
        model_name="default",
        memory=IRAiMemoryConfig(
            short_term=IRAiShortTermMemoryConfig(window=7, store="chat_long"),
            recall=[IRAiRecallRule(source="short_term", count=7)],
        ),
    )
    registry = ModelRegistry()
    registry.register_model("default", provider_name=None)
    router = ModelRouter(registry)

    execute_ai_call_with_registry(ai_call, registry, router, ctx)

    assert backend.history_calls == [("support_bot", "req-1", 7)]
    assert backend.append_calls
MODEL_BLOCK = (
    'model "gpt-4.1-mini":\n'
    '  provider "dummy"\n'
    "\n"
)
