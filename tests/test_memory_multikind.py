import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.ir import (
    IRAiCall,
    IRAiLongTermMemoryConfig,
    IRAiMemoryConfig,
    IRAiProfileMemoryConfig,
    IRAiRecallRule,
    IRAiShortTermMemoryConfig,
    IRMemoryPipelineStep,
    ast_to_ir,
    IRError,
)
from namel3ss.memory.conversation import InMemoryConversationMemoryBackend
from namel3ss.parser import parse_source
from namel3ss.runtime.context import ExecutionContext, execute_ai_call_with_registry


def test_parse_multi_kind_memory_config(monkeypatch):
    stores = {
        "default_memory": {"kind": "in_memory"},
        "chat_long": {"kind": "in_memory"},
        "user_profile": {"kind": "in_memory"},
    }
    monkeypatch.setenv("N3_MEMORY_STORES_JSON", json.dumps(stores))
    source = MODEL_BLOCK + (
        'ai is "support_bot":\n'
        '  model is "gpt-4.1-mini"\n'
        "  memory:\n"
        "    kinds:\n"
        "      short_term:\n"
        "        window is 12\n"
        "      long_term:\n"
        '        store is "chat_long"\n'
        "      profile:\n"
        '        store is "user_profile"\n'
        "        extract_facts is true\n"
        "    recall:\n"
        "      - source is \"short_term\"\n"
        "        count is 10\n"
        "      - source is \"long_term\"\n"
        "        top_k is 5\n"
        "      - source is \"profile\"\n"
        "        include is true\n"
    )
    module = parse_source(source)
    program = ast_to_ir(module)
    mem_cfg = program.ai_calls["support_bot"].memory
    assert mem_cfg is not None
    assert mem_cfg.short_term is not None
    assert mem_cfg.short_term.window == 12
    assert mem_cfg.long_term is not None
    assert mem_cfg.long_term.store == "chat_long"
    assert mem_cfg.profile is not None
    assert mem_cfg.profile.store == "user_profile"
    assert mem_cfg.profile.extract_facts is True
    assert len(mem_cfg.recall) == 3
    assert mem_cfg.recall[0].source == "short_term"
    assert mem_cfg.recall[1].top_k == 5


def test_recall_missing_kind_raises():
    source = MODEL_BLOCK + (
        'ai is "support_bot":\n'
        '  model is "gpt-4.1-mini"\n'
        "  memory:\n"
        "    recall:\n"
        "      - source is \"long_term\"\n"
        "        top_k is 5\n"
    )
    module = parse_source(source)
    with pytest.raises(IRError) as excinfo:
        ast_to_ir(module)
    assert "N3L-1202" in str(excinfo.value)


def test_memory_pipeline_parsing(monkeypatch):
    stores = {
        "default_memory": {"kind": "in_memory"},
        "chat_long": {"kind": "in_memory"},
        "user_profile": {"kind": "in_memory"},
    }
    monkeypatch.setenv("N3_MEMORY_STORES_JSON", json.dumps(stores))
    source = MODEL_BLOCK + (
        'ai is "support_bot":\n'
        '  model is "gpt-4.1-mini"\n'
        "  memory:\n"
        "    kinds:\n"
        "      long_term:\n"
        '        store is "chat_long"\n'
        "        pipeline:\n"
        '          - step is "summarize_session"\n'
        '            type is "llm_summarizer"\n'
        "            max_tokens is 256\n"
        "      profile:\n"
        '        store is "user_profile"\n'
        "        pipeline:\n"
        '          - step is "extract_facts"\n'
        '            type is "llm_fact_extractor"\n'
    )
    module = parse_source(source)
    program = ast_to_ir(module)
    mem_cfg = program.ai_calls["support_bot"].memory
    assert mem_cfg.long_term is not None
    assert mem_cfg.long_term.pipeline is not None
    assert mem_cfg.long_term.pipeline[0].name == "summarize_session"
    assert mem_cfg.long_term.pipeline[0].type == "llm_summarizer"
    assert mem_cfg.long_term.pipeline[0].max_tokens == 256
    assert mem_cfg.profile is not None
    assert mem_cfg.profile.pipeline is not None
    assert mem_cfg.profile.pipeline[0].type == "llm_fact_extractor"


def test_memory_pipeline_invalid_type(monkeypatch):
    stores = {
        "default_memory": {"kind": "in_memory"},
        "chat_long": {"kind": "in_memory"},
    }
    monkeypatch.setenv("N3_MEMORY_STORES_JSON", json.dumps(stores))
    source = MODEL_BLOCK + (
        'ai is "support_bot":\n'
        '  model is "gpt-4.1-mini"\n'
        "  memory:\n"
        "    kinds:\n"
        "      long_term:\n"
        '        store is "chat_long"\n'
        "        pipeline:\n"
        '          - step is "custom"\n'
        '            type is "custom_foo"\n'
    )
    module = parse_source(source)
    with pytest.raises(IRError) as excinfo:
        ast_to_ir(module)
    assert "N3L-1203" in str(excinfo.value)


def test_memory_policy_fields_parsing(monkeypatch):
    stores = {
        "default_memory": {"kind": "in_memory"},
        "chat_long": {"kind": "in_memory"},
    }
    monkeypatch.setenv("N3_MEMORY_STORES_JSON", json.dumps(stores))
    source = MODEL_BLOCK + (
        'ai is "support_bot":\n'
        '  model is "gpt-4.1-mini"\n'
        "  memory:\n"
        "    kinds:\n"
        "      long_term:\n"
        '        store is "chat_long"\n'
        "        retention_days is 365\n"
        '        pii_policy is "strip-email-ip"\n'
        '        scope is "per_user"\n'
    )
    module = parse_source(source)
    program = ast_to_ir(module)
    mem_cfg = program.ai_calls["support_bot"].memory
    assert mem_cfg.long_term is not None
    assert mem_cfg.long_term.retention_days == 365
    assert mem_cfg.long_term.pii_policy == "strip-email-ip"
    assert mem_cfg.long_term.scope == "per_user"


def test_invalid_pii_policy_raises(monkeypatch):
    stores = {
        "default_memory": {"kind": "in_memory"},
        "chat_long": {"kind": "in_memory"},
    }
    monkeypatch.setenv("N3_MEMORY_STORES_JSON", json.dumps(stores))
    source = MODEL_BLOCK + (
        'ai is "support_bot":\n'
        '  model is "gpt-4.1-mini"\n'
        "  memory:\n"
        "    kinds:\n"
        "      long_term:\n"
        '        store is "chat_long"\n'
        '        pii_policy is "custom_foo"\n'
    )
    module = parse_source(source)
    with pytest.raises(IRError) as excinfo:
        ast_to_ir(module)
    assert "N3L-1204" in str(excinfo.value)


def test_invalid_memory_scope_raises(monkeypatch):
    stores = {
        "default_memory": {"kind": "in_memory"},
        "chat_long": {"kind": "in_memory"},
    }
    monkeypatch.setenv("N3_MEMORY_STORES_JSON", json.dumps(stores))
    source = MODEL_BLOCK + (
        'ai is "support_bot":\n'
        '  model is "gpt-4.1-mini"\n'
        "  memory:\n"
        "    kinds:\n"
        "      long_term:\n"
        '        store is "chat_long"\n'
        '        scope is "tenant_level"\n'
    )
    module = parse_source(source)
    with pytest.raises(IRError) as excinfo:
        ast_to_ir(module)
    assert "N3L-1205" in str(excinfo.value)


def test_runtime_short_and_long_term_recall(monkeypatch):
    short_backend = InMemoryConversationMemoryBackend()
    long_backend = InMemoryConversationMemoryBackend()
    session_id = "session-1"
    ai_name = "support_bot"

    # Populate short-term history with four messages.
    short_backend.append_turns(
        ai_name,
        session_id,
        [
            {"role": "user", "content": "u1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "u2"},
            {"role": "assistant", "content": "a2"},
        ],
    )

    # Populate long-term store.
    long_backend.append_turns(
        f"{ai_name}::long_term",
        session_id,
        [
            {"role": "system", "content": "lt1"},
            {"role": "system", "content": "lt2"},
            {"role": "system", "content": "lt3"},
        ],
    )

    mem_cfg = IRAiMemoryConfig(
        short_term=IRAiShortTermMemoryConfig(window=5, store="default_memory"),
        long_term=IRAiLongTermMemoryConfig(store="chat_long"),
        recall=[
            IRAiRecallRule(source="short_term", count=3),
            IRAiRecallRule(source="long_term", top_k=2),
        ],
    )
    ai_call = IRAiCall(
        name=ai_name,
        model_name="default",
        system_prompt="system prompt",
        memory=mem_cfg,
    )

    ctx = ExecutionContext(
        app_name="test",
        request_id="req-123",
        metadata={"session_id": session_id},
        memory_stores={
            "default_memory": short_backend,
            "chat_long": long_backend,
        },
    )
    ctx.user_input = "latest question"

    registry = ModelRegistry()
    registry.register_model("default", provider_name=None)
    router = ModelRouter(registry)

    result = execute_ai_call_with_registry(ai_call, registry, router, ctx)
    messages = result["provider_result"]["raw"]["messages"]

    # Expected order: system prompt + short-term (last 3) + long-term (last 2) + user message.
    assert messages[0]["content"] == "system prompt"
    extracted = [msg["content"] for msg in messages[1:-1]]
    assert extracted[:3] == ["a1", "u2", "a2"]
    assert extracted[3:5] == ["lt2", "lt3"]
    assert messages[-1]["content"] == "latest question"

    # Short-term backend should have appended the new turn.
    updated_short = short_backend.load_history(ai_name, session_id, 10)
    assert updated_short[-2]["content"] == "latest question"


def test_runtime_profile_recall_included(monkeypatch):
    profile_backend = InMemoryConversationMemoryBackend()
    session_id = "session-profile"
    ai_name = "support_bot"

    profile_backend.append_turns(
        f"{ai_name}::profile",
        session_id,
        [
            {"role": "system", "content": "Loves football"},
            {"role": "system", "content": "Prefers concise replies"},
        ],
    )

    mem_cfg = IRAiMemoryConfig(
        profile=IRAiProfileMemoryConfig(store="user_profile", extract_facts=True),
        recall=[IRAiRecallRule(source="profile", include=True)],
    )
    ai_call = IRAiCall(
        name=ai_name,
        model_name="default",
        memory=mem_cfg,
    )
    ctx = ExecutionContext(
        app_name="test",
        request_id="req-profile",
        metadata={"session_id": session_id},
        memory_stores={"user_profile": profile_backend},
    )
    ctx.user_input = "Tell me something new."

    registry = ModelRegistry()
    registry.register_model("default", provider_name=None)
    router = ModelRouter(registry)

    result = execute_ai_call_with_registry(ai_call, registry, router, ctx)
    messages = result["provider_result"]["raw"]["messages"]

    # Ensure profile snippet included before user message.
    profile_message = messages[-2]
    assert profile_message["role"] == "system"
    assert "User profile" in profile_message["content"]
    assert "Loves football" in profile_message["content"]

    # Facts should be appended when extract_facts is true.
    updated_profile = profile_backend.load_history(f"{ai_name}::profile", session_id, 10)
    assert updated_profile[-1]["content"] == "Tell me something new."


class RecordingLongTermBackend(InMemoryConversationMemoryBackend):
    def __init__(self) -> None:
        super().__init__()
        self.summary_calls: list[tuple[str, str, str]] = []

    def append_summary(self, ai_id: str, session_id: str, summary: str) -> None:
        self.summary_calls.append((ai_id, session_id, summary))
        super().append_summary(ai_id, session_id, summary)


class RecordingProfileBackend(InMemoryConversationMemoryBackend):
    def __init__(self) -> None:
        super().__init__()
        self.fact_calls: list[tuple[str, str, list[str]]] = []

    def append_facts(self, ai_id: str, session_id: str, facts: list[str]) -> None:
        self.fact_calls.append((ai_id, session_id, list(facts)))
        super().append_facts(ai_id, session_id, facts)


def test_runtime_long_term_pipeline_runs_summarizer(monkeypatch):
    short_backend = InMemoryConversationMemoryBackend()
    long_backend = RecordingLongTermBackend()
    session_id = "session-sum"
    ai_name = "support_bot"

    mem_cfg = IRAiMemoryConfig(
        short_term=IRAiShortTermMemoryConfig(window=5, store="default_memory"),
        long_term=IRAiLongTermMemoryConfig(
            store="chat_long",
            pipeline=[IRMemoryPipelineStep(name="summarize_session", type="llm_summarizer", max_tokens=128)],
        ),
        recall=[IRAiRecallRule(source="short_term", count=3)],
    )
    ai_call = IRAiCall(
        name=ai_name,
        model_name="default",
        memory=mem_cfg,
    )
    ctx = ExecutionContext(
        app_name="test",
        request_id="req-sum",
        metadata={"session_id": session_id},
        memory_stores={
            "default_memory": short_backend,
            "chat_long": long_backend,
        },
    )
    ctx.user_input = "Summarize our progress."

    monkeypatch.setattr(
        "namel3ss.runtime.context._invoke_pipeline_model",
        lambda provider, model, messages: "summary text",
    )

    registry = ModelRegistry()
    registry.register_model("default", provider_name=None)
    router = ModelRouter(registry)

    execute_ai_call_with_registry(ai_call, registry, router, ctx)

    assert long_backend.summary_calls
    assert long_backend.summary_calls[0][2] == "summary text"


def test_runtime_profile_pipeline_runs_fact_extractor(monkeypatch):
    profile_backend = RecordingProfileBackend()
    session_id = "session-facts"
    ai_name = "support_bot"

    mem_cfg = IRAiMemoryConfig(
        profile=IRAiProfileMemoryConfig(
            store="user_profile",
            pipeline=[IRMemoryPipelineStep(name="extract", type="llm_fact_extractor")],
        ),
        recall=[IRAiRecallRule(source="profile", include=True)],
    )
    ai_call = IRAiCall(
        name=ai_name,
        model_name="default",
        memory=mem_cfg,
    )
    ctx = ExecutionContext(
        app_name="test",
        request_id="req-facts",
        metadata={"session_id": session_id},
        memory_stores={"user_profile": profile_backend},
    )
    ctx.user_input = "I live in Kampala and love football."

    monkeypatch.setattr(
        "namel3ss.runtime.context._invoke_pipeline_model",
        lambda provider, model, messages: "- User lives in Kampala\n- User likes football",
    )

    registry = ModelRegistry()
    registry.register_model("default", provider_name=None)
    router = ModelRouter(registry)

    execute_ai_call_with_registry(ai_call, registry, router, ctx)

    assert profile_backend.fact_calls
    ai_id, sess, facts = profile_backend.fact_calls[0]
    assert ai_id == f"{ai_name}::profile"
    assert sess == session_id
    assert "User lives in Kampala" in facts


def test_long_term_per_user_scope_shares_history(monkeypatch):
    _install_dummy_provider(monkeypatch)
    short_backend = InMemoryConversationMemoryBackend()
    long_backend = InMemoryConversationMemoryBackend()
    mem_cfg = IRAiMemoryConfig(
        short_term=IRAiShortTermMemoryConfig(window=3, store="default_memory"),
        long_term=IRAiLongTermMemoryConfig(store="chat_long", scope="per_user"),
        recall=[IRAiRecallRule(source="long_term", top_k=5)],
    )
    ai_call = IRAiCall(name="support_bot", model_name="default", memory=mem_cfg)
    memory_stores = {
        "default_memory": short_backend,
        "chat_long": long_backend,
    }
    registry = ModelRegistry()
    registry.register_model("default", provider_name="dummy")
    router = ModelRouter(registry)
    ctx1 = ExecutionContext(
        app_name="test",
        request_id="req-1",
        metadata={"session_id": "sess_a", "user_id": "user-123"},
        memory_stores=memory_stores,
    )
    ctx1.user_input = "First question"
    execute_ai_call_with_registry(ai_call, registry, router, ctx1)
    ctx2 = ExecutionContext(
        app_name="test",
        request_id="req-2",
        metadata={"session_id": "sess_b", "user_id": "user-123"},
        memory_stores=memory_stores,
    )
    ctx2.user_input = "Second question"
    result = execute_ai_call_with_registry(ai_call, registry, router, ctx2)
    messages = result["provider_result"]["raw"]["messages"]
    combined = " ".join(msg["content"] for msg in messages)
    assert "First question" in combined


def test_short_term_retention_filters_history(monkeypatch):
    _install_dummy_provider(monkeypatch)
    backend = InMemoryConversationMemoryBackend()
    mem_cfg = IRAiMemoryConfig(
        short_term=IRAiShortTermMemoryConfig(window=5, store="default_memory", retention_days=1),
        recall=[IRAiRecallRule(source="short_term", count=5)],
    )
    ai_call = IRAiCall(name="support_bot", model_name="default", memory=mem_cfg)
    memory_stores = {"default_memory": backend}
    backend.append_turns(
        "support_bot",
        "sess_ret",
        [{"role": "user", "content": "Old message"}],
        user_id="user-ret",
    )
    backend._store[("support_bot", "sess_ret")][0]["created_at"] = (
        datetime.now(timezone.utc) - timedelta(days=2)
    ).isoformat().replace("+00:00", "Z")
    backend.append_turns(
        "support_bot",
        "sess_ret",
        [{"role": "assistant", "content": "Recent"}],
        user_id="user-ret",
    )
    ctx = ExecutionContext(
        app_name="test",
        request_id="req-ret",
        metadata={"session_id": "sess_ret", "user_id": "user-ret"},
        memory_stores=memory_stores,
    )
    ctx.user_input = "Latest question"
    registry = ModelRegistry()
    registry.register_model("default", provider_name="dummy")
    router = ModelRouter(registry)
    result = execute_ai_call_with_registry(ai_call, registry, router, ctx)
    messages = result["provider_result"]["raw"]["messages"]
    concatenated = " ".join(msg["content"] for msg in messages)
    assert "Old message" not in concatenated


def test_pii_scrubbing_applies_to_long_term(monkeypatch):
    _install_dummy_provider(monkeypatch)
    short_backend = InMemoryConversationMemoryBackend()
    long_backend = InMemoryConversationMemoryBackend()
    mem_cfg = IRAiMemoryConfig(
        short_term=IRAiShortTermMemoryConfig(window=2, store="default_memory"),
        long_term=IRAiLongTermMemoryConfig(store="chat_long", pii_policy="strip-email-ip"),
        recall=[IRAiRecallRule(source="short_term", count=2)],
    )
    ai_call = IRAiCall(name="support_bot", model_name="default", memory=mem_cfg)
    memory_stores = {
        "default_memory": short_backend,
        "chat_long": long_backend,
    }
    ctx = ExecutionContext(
        app_name="test",
        request_id="req-pii",
        metadata={"session_id": "sess_pii", "user_id": "user-pii"},
        memory_stores=memory_stores,
    )
    ctx.user_input = "Email me at john@example.com from 192.168.0.1"
    registry = ModelRegistry()
    registry.register_model("default", provider_name="dummy")
    router = ModelRouter(registry)
    execute_ai_call_with_registry(ai_call, registry, router, ctx)
    history = long_backend.get_full_history(f"{ai_call.name}::long_term", "user:user-pii")
    combined = " ".join(turn.get("content", "") for turn in history)
    assert "[email]" in combined
    assert "[ip]" in combined
    assert "john@example.com" not in combined


MODEL_BLOCK = (
    'model "gpt-4.1-mini":\n'
    '  provider "dummy"\n'
    "\n"
)


def _install_dummy_provider(monkeypatch):
    class DummyInvocation:
        def __init__(self, messages):
            self.messages = [dict(msg) for msg in messages]
            self.raw = {"messages": self.messages}
            self.text = "ok"

        def to_dict(self):
            return {"raw": self.raw, "messages": self.messages}

    class DummyProvider:
        def invoke(self, messages, model, tools=None):
            return DummyInvocation(messages)

    monkeypatch.setattr(
        ModelRegistry,
        "get_provider_for_model",
        lambda self, model_name: DummyProvider(),
        raising=False,
    )
    monkeypatch.setattr(
        ModelRegistry,
        "get_model_config",
        lambda self, model_name: SimpleNamespace(model=model_name),
        raising=False,
    )
