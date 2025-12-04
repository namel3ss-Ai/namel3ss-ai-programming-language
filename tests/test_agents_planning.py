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


def test_basic_planning_parses_numbered_steps_and_rationale():
    output = "1. Collect requirements\n2. Evaluate constraints\n3. Produce deliverables\n\nRationale: This plan ensures efficiency and clarity."
    runner, provider = build_runner([output])
    ctx = ExecutionContext(app_name="demo", request_id="req")
    goal = AgentGoal(description="Ship a feature", constraints={})

    plan = runner.plan(goal, ctx, agent_id="helper")

    assert provider.calls == 1
    assert plan.steps == ["Collect requirements", "Evaluate constraints", "Produce deliverables"]
    assert plan.rationale == "This plan ensures efficiency and clarity."
    assert plan.raw_output == output


def test_constraints_appear_in_prompt():
    runner, provider = build_runner(["1. Do X\nRationale: ok"])
    ctx = ExecutionContext(app_name="demo", request_id="req")
    goal = AgentGoal(description="Test goal", constraints={"budget": "low", "deadline": "soon"})

    _ = runner.plan(goal, ctx, agent_id="helper")

    prompt = provider.last_messages[-1]["content"]
    assert "Test goal" in prompt
    assert "budget" in prompt and "low" in prompt
    assert "deadline" in prompt and "soon" in prompt


def test_parses_bullet_and_numbered_lists():
    output = "- First step\n- Second step\n- Third step\n\nRationale: Bullet list."
    runner, provider = build_runner([output])
    ctx = ExecutionContext(app_name="demo", request_id="req")
    goal = AgentGoal(description="Bullets", constraints={})

    plan = runner.plan(goal, ctx, agent_id="helper")
    assert plan.steps == ["First step", "Second step", "Third step"]

    output_numbered = "1) One\n2) Two\n\nRationale: Numbered."
    runner2, provider2 = build_runner([output_numbered])
    plan2 = runner2.plan(goal, ctx, agent_id="helper")
    assert plan2.steps == ["One", "Two"]


class MemorySpy:
    def __init__(self):
        self.events = []

    def record_conversation(self, space: str, message: str, role: str):
        self.events.append({"space": space, "message": message, "role": role})
        return {"space": space, "message": message, "role": role}


def test_memory_hook_records_plan_event():
    runner, provider = build_runner(["1. Step\nRationale: ok"])
    ctx = ExecutionContext(app_name="demo", request_id="req")
    ctx.memory_engine = MemorySpy()
    goal = AgentGoal(description="Mem goal", constraints={})

    _ = runner.plan(goal, ctx, agent_id="helper")

    assert provider.calls == 1
    assert any("agent_plan_generated" in event["message"] for event in ctx.memory_engine.events)


def test_plan_does_not_affect_reflection_or_debate():
    runner, provider = build_runner(["1. Step\nRationale: ok"])
    ctx = ExecutionContext(app_name="demo", request_id="req")
    goal = AgentGoal(description="Compat goal", constraints={})

    plan = runner.plan(goal, ctx, agent_id="helper")
    assert plan.steps[0] == "Step"
    # Reflection and debate paths are untouched; ensure router calls only once for planning.
    assert provider.calls == 1
