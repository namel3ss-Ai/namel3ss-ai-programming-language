from textwrap import dedent

import pytest

from namel3ss.errors import IRError
from namel3ss.ir import DEFAULT_SHORT_TERM_WINDOW, ast_to_ir
from namel3ss.parser import parse_source


@pytest.fixture(autouse=True)
def _install_dummy_provider(monkeypatch):
    monkeypatch.setenv("N3_PROVIDERS_JSON", '{"dummy":{"type":"openai"}}')
    monkeypatch.setenv(
        "N3_MEMORY_STORES_JSON",
        '{"default_memory":{"kind":"in_memory"},"chat_long":{"kind":"in_memory"},"session_store":{"kind":"in_memory"}}',
    )


MODEL_BLOCK = dedent(
    """
    model "gpt-4.1-mini":
      provider "dummy"

    """
)


def test_memory_profile_short_term_defaults():
    source = MODEL_BLOCK + dedent(
        """
        memory profile is "conversational_short":
          kinds:
            short_term

        ai is "support_bot":
          model is "gpt-4.1-mini"
          use memory profile "conversational_short"
        """
    )
    program = ast_to_ir(parse_source(source))
    mem = program.ai_calls["support_bot"].memory
    assert mem is not None
    assert mem.short_term is not None
    assert mem.short_term.window == DEFAULT_SHORT_TERM_WINDOW
    assert mem.short_term.scope == "per_session"
    assert mem.recall and mem.recall[0].source == "short_term"
    assert mem.recall[0].count == DEFAULT_SHORT_TERM_WINDOW


def test_memory_profile_merging_and_inline_override():
    source = MODEL_BLOCK + dedent(
        """
        memory profile is "short_default":
          kinds:
            short_term:
              window is 16

        memory profile is "long_profile":
          kinds:
            long_term:
              store is "chat_long"

        ai is "support_bot":
          model is "gpt-4.1-mini"
          use memory profile "short_default"
          use memory profile "long_profile"
          memory:
            kinds:
              short_term:
                window is 32
                store is "session_store"
        """
    )
    program = ast_to_ir(parse_source(source))
    mem = program.ai_calls["support_bot"].memory
    assert mem is not None
    assert mem.short_term is not None
    assert mem.short_term.window == 32
    assert mem.short_term.store == "session_store"
    assert mem.long_term is not None
    assert mem.long_term.store == "chat_long"


def test_duplicate_memory_profile_names_error():
    source = MODEL_BLOCK + dedent(
        """
        memory profile is "dup_profile":
          kinds:
            short_term

        memory profile is "dup_profile":
          kinds:
            short_term:
              window is 25
        """
    )
    with pytest.raises(IRError) as excinfo:
        ast_to_ir(parse_source(source))
    assert "memory profile named 'dup_profile'" in str(excinfo.value)


def test_unknown_memory_profile_reference():
    source = MODEL_BLOCK + dedent(
        """
        memory profile is "conversational_short":
          kinds:
            short_term

        ai is "support_bot":
          model is "gpt-4.1-mini"
          use memory profile "missing_profile"
        """
    )
    with pytest.raises(IRError) as excinfo:
        ast_to_ir(parse_source(source))
    assert "uses memory profile 'missing_profile'" in str(excinfo.value)


def test_memory_kinds_accepts_bare_short_term():
    source = MODEL_BLOCK + dedent(
        """
        ai is "support_bot":
          model is "gpt-4.1-mini"
          memory:
            kinds:
              short_term
        """
    )
    program = ast_to_ir(parse_source(source))
    mem = program.ai_calls["support_bot"].memory
    assert mem is not None
    assert mem.short_term is not None
    assert mem.short_term.window == DEFAULT_SHORT_TERM_WINDOW
    assert mem.recall and mem.recall[0].count == DEFAULT_SHORT_TERM_WINDOW


def test_memory_kinds_accepts_empty_short_term_header():
    source = MODEL_BLOCK + dedent(
        """
        ai is "support_bot":
          model is "gpt-4.1-mini"
          memory:
            kinds:
              short_term:
        """
    )
    program = ast_to_ir(parse_source(source))
    mem = program.ai_calls["support_bot"].memory
    assert mem is not None
    assert mem.short_term is not None
    assert mem.short_term.window == DEFAULT_SHORT_TERM_WINDOW
    assert mem.recall and mem.recall[0].count == DEFAULT_SHORT_TERM_WINDOW


def test_memory_profile_with_episodic_and_semantic(monkeypatch):
    monkeypatch.setenv(
        "N3_MEMORY_STORES_JSON",
        '{"default_memory":{"kind":"in_memory"},"episode_store":{"kind":"in_memory"},"semantic_store":{"kind":"in_memory"}}',
    )
    source = MODEL_BLOCK + dedent(
        """
        memory profile is "episodic_defaults":
          kinds:
            episodic:
              store is "episode_store"

        memory profile is "semantic_defaults":
          kinds:
            semantic:
              store is "semantic_store"

        ai is "support_bot":
          model is "gpt-4.1-mini"
          use memory profile "episodic_defaults"
          use memory profile "semantic_defaults"
          memory:
            recall:
              - source is "episodic"
                top_k is 3
              - source is "semantic"
                top_k is 2
        """
    )
    program = ast_to_ir(parse_source(source))
    mem = program.ai_calls["support_bot"].memory
    assert mem is not None
    assert mem.episodic is not None and mem.episodic.store == "episode_store"
    assert mem.semantic is not None and mem.semantic.store == "semantic_store"
    sources = [rule.source for rule in mem.recall]
    assert sources == ["episodic", "semantic"]
