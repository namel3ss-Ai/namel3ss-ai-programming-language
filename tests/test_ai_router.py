from namel3ss.ai.config import GlobalAIConfig
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter


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
