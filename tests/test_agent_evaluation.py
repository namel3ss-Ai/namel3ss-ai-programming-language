from namel3ss.agent.engine import AgentRunner
from namel3ss.agent.eval import run_agent_evaluation
from namel3ss.ai.providers import ModelProvider
from namel3ss.ai.models import ModelResponse
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.flows.engine import FlowEngine
from namel3ss.ir import (
    IRAgent,
    IRAgentEvaluation,
    IRAiCall,
    IRFrame,
    IRProgram,
    IRTableConfig,
)
from namel3ss.tools.registry import ToolRegistry


class StubProvider(ModelProvider):
    def __init__(self, responses):
        super().__init__("stub")
        self.responses = list(responses)
        self.calls = []
        self.supports_tools = False

    def generate(self, messages, **kwargs):
        self.calls.append({"messages": messages, "kwargs": kwargs})
        text = self.responses.pop(0)
        return ModelResponse(provider="stub", model=kwargs.get("model") or "stub-model", messages=messages, text=text, raw={"text": text})

    def stream(self, messages, **kwargs):
        raise NotImplementedError

    def chat_with_tools(self, messages, tools=None, tool_choice="auto", **kwargs):
        return self.generate(messages, **kwargs)


class StubRegistry:
    def __init__(self, provider):
        self.provider = provider
        self.provider_status = {}

    def resolve_provider_for_ai(self, ai_call):
        return self.provider, ai_call.model_name or "stub-model", "stub"


def _build_engine_with_agent_eval(responses):
    program = IRProgram()
    program.ai_calls["support"] = IRAiCall(name="support", model_name="stub-model")
    program.agents["support"] = IRAgent(name="support", goal="Answer", system_prompt=None)
    program.frames["cases"] = IRFrame(
        name="cases",
        source_kind="memory",
        select_cols=["question", "expected"],
        table_config=IRTableConfig(primary_key="question", display_columns=["question"]),
    )
    program.agent_evaluations["support_eval"] = IRAgentEvaluation(
        name="support_eval",
        agent="support",
        dataset_frame="cases",
        input_mapping={"question": "question"},
        expected_answer_column="expected",
        metrics=["answer_correctness", "latency_seconds", "error_rate"],
    )
    provider = StubProvider(responses)
    registry = StubRegistry(provider)
    router = ModelRouter(ModelRegistry())
    tool_registry = ToolRegistry()
    agent_runner = AgentRunner(program, registry, tool_registry, router)
    engine = FlowEngine(
        program=program,
        model_registry=registry,
        tool_registry=tool_registry,
        agent_runner=agent_runner,
        router=router,
    )
    return engine, provider


def test_agent_evaluation_runs(monkeypatch):
    engine, provider = _build_engine_with_agent_eval(["blue", "red"])
    engine.frame_registry.insert("cases", {"question": "favorite colour?", "expected": "blue"})
    engine.frame_registry.insert("cases", {"question": "other?", "expected": "green"})

    eval_cfg = engine.program.agent_evaluations["support_eval"]
    result = run_agent_evaluation(engine.program, eval_cfg, engine)

    assert result.num_rows == 2
    # First row matches, second does not.
    assert result.metrics.get("answer_correctness") == 0.5
    assert result.metrics.get("error_rate") == 0.0
    assert provider.calls  # provider invoked
