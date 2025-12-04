from __future__ import annotations

from namel3ss.agent.engine import AgentRunner
from namel3ss.agent.planning import AgentGoal
from namel3ss.ai.models import ModelResponse, ModelStreamChunk
from namel3ss.ai.providers import ModelProvider
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.ir import IRAgent, IRModel, IRProgram
from namel3ss.runtime.context import ExecutionContext
from namel3ss.tools.registry import ToolRegistry


class FakeProvider(ModelProvider):
    def __init__(self, outputs):
        super().__init__(name="fake", default_model="fake-model")
        self.outputs = list(outputs)
        self.calls = 0
        self.last_messages = None

    def _next_text(self) -> str:
        if not self.outputs:
            return ""
        idx = min(self.calls, len(self.outputs) - 1)
        return str(self.outputs[idx])

    def generate(self, messages, **kwargs) -> ModelResponse:
        self.last_messages = messages
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


def build_runner(outputs):
    program = IRProgram(
        agents={"helper": IRAgent(name="helper")},
        models={"model": IRModel(name="model", provider="fake")},
    )
    registry = ModelRegistry()
    registry.register_model("model", provider_name="fake")
    provider = FakeProvider(outputs)
    registry.providers["model"] = provider
    router = ModelRouter(registry)
    tools = ToolRegistry()
    runner = AgentRunner(program, registry, tools, router)
    return runner, provider


def test_basic_evaluation_parses_json():
    output = '{"score": 0.8, "reasons": "Answer covers key constraints.", "rubric": "Correctness, completeness, clarity."}'
    runner, provider = build_runner([output])
    ctx = ExecutionContext(app_name="demo", request_id="req")
    goal = AgentGoal(description="Build a plan for X", constraints={"deadline": "soon"})
    eval_result = runner.evaluate_answer(goal, "Some answer", ctx, agent_id="helper")

    assert provider.calls == 1
    assert abs(eval_result.score - 0.8) < 1e-6
    assert eval_result.reasons == "Answer covers key constraints."
    assert eval_result.rubric == "Correctness, completeness, clarity."
    assert eval_result.raw_output == output


def test_parsing_handles_pattern_format():
    output = "SCORE: 0.6\nREASONS: Adequate coverage.\nRUBRIC: brevity"
    runner, provider = build_runner([output])
    ctx = ExecutionContext(app_name="demo", request_id="req")
    goal = AgentGoal(description="Test parsing", constraints={})

    eval_result = runner.evaluate_answer(goal, "Another answer", ctx, agent_id="helper")

    assert abs(eval_result.score - 0.6) < 1e-6
    assert "Adequate" in eval_result.reasons
    assert eval_result.rubric == "brevity"


def test_score_normalization_from_ten_scale():
    output = '{"score": 8, "reasons": "Good", "rubric": "ten scale"}'
    runner, provider = build_runner([output])
    ctx = ExecutionContext(app_name="demo", request_id="req")
    goal = AgentGoal(description="Normalize", constraints={})

    eval_result = runner.evaluate_answer(goal, "Ans", ctx, agent_id="helper")
    assert abs(eval_result.score - 0.8) < 1e-6


class MemorySpy:
    def __init__(self):
        self.events = []

    def record_conversation(self, space: str, message: str, role: str):
        self.events.append({"space": space, "message": message, "role": role})
        return {"space": space, "message": message, "role": role}


def test_memory_hook_records_evaluation_event():
    output = '{"score": 1, "reasons": "Perfect", "rubric": "simple"}'
    runner, provider = build_runner([output])
    ctx = ExecutionContext(app_name="demo", request_id="req")
    ctx.memory_engine = MemorySpy()
    goal = AgentGoal(description="Memory goal", constraints={})

    runner.evaluate_answer(goal, "Answer", ctx, agent_id="helper")
    assert any("agent_evaluation" in ev["message"] for ev in ctx.memory_engine.events)


def test_other_features_unchanged_without_evaluation():
    output = '{"score": 1, "reasons": "Perfect", "rubric": "simple"}'
    runner, provider = build_runner([output])
    ctx = ExecutionContext(app_name="demo", request_id="req")
    ctx.memory_engine = MemorySpy()
    # running plan should not record evaluation events
    runner.plan(AgentGoal(description="plan", constraints={}), ctx, agent_id="helper")
    assert all("agent_evaluation" not in ev["message"] for ev in ctx.memory_engine.events)
