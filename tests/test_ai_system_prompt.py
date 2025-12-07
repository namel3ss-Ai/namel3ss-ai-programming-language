import pytest

from namel3ss import ast_nodes
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.errors import ParseError
from namel3ss.ir import IRAiCall
from namel3ss.parser import parse_source
from namel3ss.runtime.context import ExecutionContext, execute_ai_call_with_registry


def test_ai_block_with_system_prompt_parses():
    module = parse_source(
        'ai "bot":\n'
        '  model "default"\n'
        '  system "You are helpful."\n'
        '  input from user_question\n'
    )
    ai_decl = next(d for d in module.declarations if isinstance(d, ast_nodes.AICallDecl))
    assert ai_decl.system_prompt == "You are helpful."


def test_system_prompt_invalid_in_page():
    with pytest.raises(ParseError):
        parse_source(
            'page "home":\n'
            '  system "nope"\n'
        )


def test_duplicate_system_prompt_rejected():
    with pytest.raises(ParseError):
        parse_source(
            'ai "bot":\n'
            '  model "default"\n'
            '  system "first"\n'
            '  system "second"\n'
        )


def test_runtime_includes_system_message_first():
    registry = ModelRegistry()
    registry.register_model("default", "dummy")
    router = ModelRouter(registry)
    ai_call = IRAiCall(
        name="bot",
        model_name="default",
        input_source="hi there",
        system_prompt="You are a helper.",
    )
    ctx = ExecutionContext(app_name="test", request_id="req-1", user_input=None)
    result = execute_ai_call_with_registry(ai_call, registry, router, ctx)
    provider_result = result["provider_result"]
    messages = provider_result["messages"]
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "You are a helper."
    assert messages[1]["role"] == "user"
