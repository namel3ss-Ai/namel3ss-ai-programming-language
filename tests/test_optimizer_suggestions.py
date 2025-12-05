import asyncio
from datetime import datetime, timezone

from namel3ss.ai.models import ModelResponse
from namel3ss.ai.providers import ModelProvider
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.optimizer.models import (
    EvaluationCase,
    EvaluationRun,
    SuggestionStatus,
    TargetType,
)
from namel3ss.optimizer.suggestions import SuggestionEngine


class FakeProvider(ModelProvider):
    def __init__(self, text: str):
        super().__init__("fake")
        self.text = text

    def generate(self, messages, **kwargs):
        return ModelResponse(provider="fake", model="fake", messages=messages, text=self.text, raw={})

    def stream(self, messages, **kwargs):
        return iter([])


def build_router(text: str):
    registry = ModelRegistry()
    registry.register_model("fake", provider_name="fake")
    router = ModelRouter(registry)
    router.registry.providers["fake"] = FakeProvider(text)
    return router


def test_suggestion_engine_parses_json():
    run = EvaluationRun(
        id="r1",
        target_type=TargetType.FLOW,
        target_name="demo",
        created_at=datetime.now(timezone.utc),
        cases=[EvaluationCase(id="c1", input={})],
        metrics_summary={"avg_latency": 1.0},
        raw_results=[],
    )
    text = '{"suggestions":[{"description":"Switch model","change_spec":{"type":"model_switch","model":"gpt"}}]}'
    engine = SuggestionEngine(build_router(text))
    suggestions = asyncio.run(engine.generate_suggestions_for_evaluation(run))
    assert suggestions
    assert suggestions[0].change_spec["type"] == "model_switch"
    assert suggestions[0].status == SuggestionStatus.PENDING
