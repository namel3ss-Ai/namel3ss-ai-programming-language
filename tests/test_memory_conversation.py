import pytest

from namel3ss import ast_nodes
from namel3ss.parser import parse_source
from namel3ss.ir import IRMemory, IRProgram, IRAiCall
from namel3ss.ir import ast_to_ir, IRError
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.runtime.context import ExecutionContext, execute_ai_call_with_registry
from namel3ss.memory.engine import MemoryEngine
from namel3ss.memory.models import MemorySpaceConfig, MemoryType


def test_parse_memory_and_ai_reference():
    module = parse_source(
        'memory "support_chat":\n'
        '  type "conversation"\n'
        '  retention "30 days"\n'
        '\n'
        'ai "bot":\n'
        '  model "default"\n'
        '  memory "support_chat"\n'
    )
    memories = [d for d in module.declarations if isinstance(d, ast_nodes.MemoryDecl)]
    assert memories and memories[0].retention == "30 days"
    ai = next(d for d in module.declarations if isinstance(d, ast_nodes.AICallDecl))
    assert ai.memory_name == "support_chat"


def test_ai_unknown_memory_errors():
    module = ast_nodes.Module(
        declarations=[
            ast_nodes.AICallDecl(name="bot", model_name="default", memory_name="missing"),
        ]
    )
    with pytest.raises(IRError):
        ast_to_ir(module)


def _make_context_with_memory(memory_name: str, request_id: str = "req1") -> tuple[ExecutionContext, MemoryEngine]:
    mem_engine = MemoryEngine(
        spaces=[MemorySpaceConfig(name=memory_name, type=MemoryType.CONVERSATION)]
    )
    ctx = ExecutionContext(app_name="test", request_id=request_id, memory_engine=mem_engine)
    return ctx, mem_engine


def test_conversation_accumulates_across_calls():
    memory_name = "chat"
    ai_call = IRAiCall(name="bot", model_name="default", memory_name=memory_name, system_prompt="be kind")
    registry = ModelRegistry()
    registry.register_model("default", provider_name=None)
    router = ModelRouter(registry)
    ctx, mem_engine = _make_context_with_memory(memory_name)

    # First call
    ctx.user_input = "hello"
    result1 = execute_ai_call_with_registry(ai_call, registry, router, ctx)
    messages1 = result1["provider_result"]["raw"]["messages"]
    assert messages1[0]["role"] == "system"
    assert len(mem_engine.get_recent(memory_name)) == 2  # user + assistant

    # Second call, same session
    ctx.user_input = "second"
    result2 = execute_ai_call_with_registry(ai_call, registry, router, ctx)
    messages2 = result2["provider_result"]["raw"]["messages"]
    assert len(messages2) >= 4  # system + prior turn + new user
    assert len(mem_engine.get_recent(memory_name)) == 4  # two turns stored


def test_conversation_isolated_by_session():
    memory_name = "chat"
    ai_call = IRAiCall(name="bot", model_name="default", memory_name=memory_name)
    registry = ModelRegistry()
    registry.register_model("default", provider_name=None)
    router = ModelRouter(registry)

    ctx1, mem_engine = _make_context_with_memory(memory_name, request_id="session1")
    ctx1.user_input = "hello"
    execute_ai_call_with_registry(ai_call, registry, router, ctx1)

    ctx2 = ExecutionContext(app_name="test", request_id="session2", memory_engine=mem_engine, user_input="hi")
    execute_ai_call_with_registry(ai_call, registry, router, ctx2)

    # Each session keeps its own turns (2 messages per call)
    assert len(mem_engine.load_conversation(memory_name, session_id="session1")) == 2
    assert len(mem_engine.load_conversation(memory_name, session_id="session2")) == 2
