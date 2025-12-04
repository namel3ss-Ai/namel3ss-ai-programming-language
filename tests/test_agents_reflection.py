from __future__ import annotations

from namel3ss.agent.engine import AgentRunner
from namel3ss.agent.models import AgentConfig
from namel3ss.agent.reflection import ReflectionConfig
from namel3ss.ai.models import ModelResponse, ModelStreamChunk
from namel3ss.ai.providers import ModelProvider
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.ir import IRAgent, IRAiCall, IRModel, IRProgram
from namel3ss.runtime.context import ExecutionContext
from namel3ss.tools.registry import ToolRegistry


class FakeProvider(ModelProvider):
    def __init__(self, outputs):
        super().__init__(name="fake", default_model="fake-model")
        self.outputs = list(outputs)
        self.calls = 0

    def _next_text(self) -> str:
        if not self.outputs:
            return ""
        idx = min(self.calls, len(self.outputs) - 1)
        return str(self.outputs[idx])

    def generate(self, messages, **kwargs) -> ModelResponse:
        text = self._next_text()
        self.calls += 1
        return ModelResponse(
            provider=self.name,
            model=self.default_model or "fake-model",
            messages=messages,
            text=text,
            raw={"messages": messages},
        )

    def stream(self, messages, **kwargs):
        yield ModelStreamChunk(
            provider=self.name,
            model=self.default_model or "fake-model",
            delta=self._next_text(),
            raw={"messages": messages},
            is_final=True,
        )


def build_runner(outputs, reflection_config: ReflectionConfig | None):
    program = IRProgram(
        agents={"helper": IRAgent(name="helper")},
        ai_calls={"ask": IRAiCall(name="ask", model_name="model", input_source="question")},
        models={"model": IRModel(name="model", provider="fake")},
    )
    registry = ModelRegistry()
    registry.register_model("model", provider_name="fake")
    provider = FakeProvider(outputs)
    registry.providers["model"] = provider
    router = ModelRouter(registry)
    tools = ToolRegistry()
    runner = AgentRunner(
        program,
        registry,
        tools,
        router,
        config=AgentConfig(reflection=reflection_config),
    )
    return runner, provider


def build_context():
    return ExecutionContext(app_name="demo", request_id="req", user_input="What is the task?")


def test_reflection_single_round_enabled():
    runner, provider = build_runner(
        ["INITIAL_ANSWER", "CRITIQUE_1", "IMPROVED_ANSWER_1"],
        ReflectionConfig(enabled=True, max_rounds=1),
    )
    result = runner.run("helper", build_context())

    assert result.final_answer == "IMPROVED_ANSWER_1"
    assert result.reflection_rounds == 1
    assert result.critiques == ["CRITIQUE_1"]
    assert result.improvements == ["IMPROVED_ANSWER_1"]
    assert provider.calls == 3  # initial + critique + improvement


def test_reflection_multiple_rounds():
    runner, provider = build_runner(
        ["INITIAL_ANSWER", "CRITIQUE_1", "IMPROVED_1", "CRITIQUE_2", "IMPROVED_2"],
        ReflectionConfig(enabled=True, max_rounds=2),
    )
    result = runner.run("helper", build_context())

    assert provider.calls == 5
    assert result.reflection_rounds == 2
    assert result.critiques == ["CRITIQUE_1", "CRITIQUE_2"]
    assert result.improvements == ["IMPROVED_1", "IMPROVED_2"]
    assert result.final_answer == "IMPROVED_2"


def test_reflection_disabled_runs_once():
    runner, provider = build_runner(["INITIAL_ONLY"], ReflectionConfig(enabled=False))
    result = runner.run("helper", build_context())

    assert provider.calls == 1
    assert result.reflection_rounds == 0
    assert result.critiques == []
    assert result.improvements == []
    assert result.final_answer == "INITIAL_ONLY"


def test_reflection_respects_zero_rounds():
    runner, provider = build_runner(["INITIAL_ANSWER"], ReflectionConfig(enabled=True, max_rounds=0))
    result = runner.run("helper", build_context())

    assert provider.calls == 1
    assert result.reflection_rounds == 0
    assert result.critiques == []
    assert result.improvements == []
    assert result.final_answer == "INITIAL_ANSWER"


class MemorySpy:
    def __init__(self):
        self.events = []

    def record_conversation(self, space: str, message: str, role: str):
        self.events.append({"space": space, "message": message, "role": role})
        return {"space": space, "message": message, "role": role}


def test_reflection_records_memory_hooks():
    runner, provider = build_runner(
        ["INITIAL", "CRITIQUE", "IMPROVED"],
        ReflectionConfig(enabled=True, max_rounds=1),
    )
    ctx = build_context()
    ctx.memory_engine = MemorySpy()

    result = runner.run("helper", ctx)

    assert provider.calls == 3
    assert result.final_answer == "IMPROVED"
    recorded_messages = [event["message"] for event in ctx.memory_engine.events]
    assert any("agent_initial_answer" in msg for msg in recorded_messages)
    assert any("agent_critique" in msg for msg in recorded_messages)
    assert any("agent_improved_answer" in msg for msg in recorded_messages)
    assert any("round=0" in msg for msg in recorded_messages if "agent_critique" in msg or "agent_improved_answer" in msg)
