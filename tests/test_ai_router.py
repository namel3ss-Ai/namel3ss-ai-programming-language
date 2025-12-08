from namel3ss.ai.config import GlobalAIConfig
from namel3ss.ai.registry import ModelRegistry, ModelConfig
from namel3ss.ai.router import ModelRouter
from namel3ss.ai.models import ModelStreamChunk, ModelResponse
from namel3ss.ai.providers import ModelProvider


def test_router_prefers_configured_provider():
    registry = ModelRegistry()
    registry.register_model("fast", "fastprov")
    registry.register_model("cheap", "dummy")
    config = GlobalAIConfig(preferred_providers=["dummy"])
    router = ModelRouter(registry, config)
    selection = router.select_model()
    assert selection.provider_name == "dummy"
    assert selection.model_name == "cheap"


def test_router_fallback_to_named_model():
    registry = ModelRegistry()
    registry.register_model("primary", "p1")
    router = ModelRouter(registry)
    selection = router.select_model(logical_name="primary")
    assert selection.model_name == "primary"
    assert selection.provider_name == "p1"


class _StreamingProvider(ModelProvider):
    def __init__(self) -> None:
        super().__init__(name="streamer", default_model="m1")

    def generate(self, messages, **kwargs):
        return ModelResponse(provider=self.name, model=self.default_model or "", messages=messages, text="full", raw={})

    def stream(self, messages, **kwargs):
        yield ModelStreamChunk(provider=self.name, model=self.default_model or "", delta="foo", raw={}, is_final=False)
        yield ModelStreamChunk(provider=self.name, model=self.default_model or "", delta="bar", raw={}, is_final=True)


def test_router_streams_from_provider():
    registry = ModelRegistry()
    registry.providers["m1"] = _StreamingProvider()
    registry.model_configs["m1"] = ModelConfig(
        name="m1", provider="streamer", model="m1"
    )
    router = ModelRouter(registry)
    chunks = list(router.stream([{"role": "user", "content": "hi"}], model="m1"))
    assert [c.delta for c in chunks] == ["foo", "bar"]
