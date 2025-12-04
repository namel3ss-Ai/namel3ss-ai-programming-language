from __future__ import annotations

from namel3ss.agent.debate import (
    DebateAgentConfig,
    DebateConfig,
    DebateEngine,
)
from namel3ss.agent.models import AgentConfig
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


def build_engine(outputs):
    program = IRProgram(
        agents={"agent_a": IRAgent(name="agent_a"), "agent_b": IRAgent(name="agent_b")},
        ai_calls={"ask": IRAiCall(name="ask", model_name="model", input_source=None)},
        models={"model": IRModel(name="model", provider="fake")},
    )
    registry = ModelRegistry()
    registry.register_model("model", provider_name="fake")
    provider = FakeProvider(outputs)
    registry.providers["model"] = provider
    router = ModelRouter(registry)
    tools = ToolRegistry()
    engine = DebateEngine(program, registry, tools, router)
    context = ExecutionContext(app_name="demo", request_id="req")
    return engine, provider, context


def test_basic_multi_agent_debate_consensus():
    outputs = [
        "A_INIT",
        "B_INIT",
        "A_R1",
        "B_R1",
        '{"consensus_summary": "CONSENSUS", "chosen_answer": "A_R1", "scores": {"agent_a": 1.0, "agent_b": 0.5}}',
    ]
    engine, provider, ctx = build_engine(outputs)
    agents = [
        DebateAgentConfig(id="agent_a", config=AgentConfig()),
        DebateAgentConfig(id="agent_b", config=AgentConfig()),
    ]
    outcome = engine.run_debate("What is the result?", agents, ctx, DebateConfig(max_rounds=1))

    assert provider.calls == 5
    assert len(outcome.transcript) == 4
    assert [(t.agent_id, t.round_index) for t in outcome.transcript] == [
        ("agent_a", 0),
        ("agent_b", 0),
        ("agent_a", 1),
        ("agent_b", 1),
    ]
    assert outcome.consensus_summary == "CONSENSUS"
    assert outcome.chosen_answer == "A_R1"
    assert outcome.scores == {"agent_a": 1.0, "agent_b": 0.5}


def test_debate_multiple_rounds():
    outputs = [
        "A_INIT",
        "B_INIT",
        "A_R1",
        "B_R1",
        "A_R2",
        "B_R2",
        '{"consensus_summary": "DONE", "chosen_answer": "B_R2", "scores": {"agent_a": 0.7, "agent_b": 1.0}}',
    ]
    engine, provider, ctx = build_engine(outputs)
    agents = [
        DebateAgentConfig(id="agent_a", config=AgentConfig()),
        DebateAgentConfig(id="agent_b", config=AgentConfig()),
    ]
    outcome = engine.run_debate("Compute", agents, ctx, DebateConfig(max_rounds=2))

    assert provider.calls == 7
    assert len(outcome.transcript) == 6  # 2 agents * (1 initial + 2 rounds)
    assert outcome.chosen_answer == "B_R2"
    assert outcome.scores == {"agent_a": 0.7, "agent_b": 1.0}


class MemorySpy:
    def __init__(self):
        self.events = []

    def record_conversation(self, space: str, message: str, role: str):
        self.events.append({"space": space, "message": message, "role": role})
        return {"space": space, "message": message, "role": role}


def test_debate_records_memory_events():
    outputs = [
        "A_INIT",
        "B_INIT",
        "A_R1",
        "B_R1",
        '{"consensus_summary": "OK", "chosen_answer": "B_R1", "scores": {"agent_a": 0.5, "agent_b": 1.0}}',
    ]
    engine, provider, ctx = build_engine(outputs)
    ctx.memory_engine = MemorySpy()
    agents = [
        DebateAgentConfig(id="agent_a", config=AgentConfig()),
        DebateAgentConfig(id="agent_b", config=AgentConfig()),
    ]
    outcome = engine.run_debate("Question?", agents, ctx, DebateConfig(max_rounds=1))

    assert provider.calls == 5
    assert outcome.chosen_answer == "B_R1"
    messages = [event["message"] for event in ctx.memory_engine.events]
    assert any("agent_debate_turn" in msg and "round=0" in msg for msg in messages)
    assert any("agent_debate_turn" in msg and "round=1" in msg for msg in messages)
    assert any("agent_debate_consensus" in msg for msg in messages)
