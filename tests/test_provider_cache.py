import time
from types import SimpleNamespace

from namel3ss.ai.providers import DummyProvider
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.ai.config import default_global_ai_config
from namel3ss.config import ProviderConfig, ProvidersConfig
from namel3ss.runtime.cache import InMemoryProviderCache, cache_get_sync, cache_set_sync
from namel3ss.runtime.context import ExecutionContext, execute_ai_call_with_registry


class CountingProvider(DummyProvider):
    def __init__(self, name: str = "dummy", default_model: str | None = None) -> None:
        super().__init__(name=name, default_model=default_model)
        self.calls = 0

    def generate(self, messages, **kwargs):  # type: ignore[override]
        self.calls += 1
        return super().generate(messages, **kwargs)


def test_ai_call_uses_provider_cache():
    providers_config = ProvidersConfig(
        default="dummy",
        providers={"dummy": ProviderConfig(type="dummy")},
    )
    provider = CountingProvider(name="dummy", default_model="dummy-model")

    class StubRegistry(ModelRegistry):
        def __init__(self, provider_instance):
            super().__init__(providers_config=providers_config)
            self._provider_instance = provider_instance
            self.provider_status = {}

        def _create_provider(self, cfg):  # type: ignore[override]
            return self._provider_instance

    registry = StubRegistry(provider)
    router = ModelRouter(registry, default_global_ai_config())
    cache = InMemoryProviderCache()

    ai_call = SimpleNamespace(
        name="greeter",
        model_name="dummy-model",
        input_source="hello",
        system_prompt=None,
        tools=[],
        memory=None,
    )
    context = ExecutionContext(app_name="test", request_id="req-1", provider_cache=cache)

    first = execute_ai_call_with_registry(ai_call, registry, router, context)
    second = execute_ai_call_with_registry(ai_call, registry, router, context)

    assert provider.calls == 1
    assert first["provider_result"] == second["provider_result"]


def test_inmemory_cache_ttl_expires():
    cache = InMemoryProviderCache()
    cache_set_sync(cache, "key", "value", ttl=0.01)
    assert cache_get_sync(cache, "key") == "value"
    time.sleep(0.02)
    assert cache_get_sync(cache, "key") is None

