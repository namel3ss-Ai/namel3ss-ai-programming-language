from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.ai.http_json_provider import HTTPJsonProvider
from namel3ss.ai.providers import DummyProvider
from namel3ss.secrets.manager import SecretsManager


def test_router_selects_models_with_env_config():
    env = {
        "N3_MODEL_FAST_PROVIDER": "http_json",
        "N3_MODEL_FAST_BASE_URL": "http://localhost/api",
        "N3_MODEL_FAST_RESPONSE_PATH": "data.message.content",
        "N3_MODEL_SLOW_PROVIDER": "dummy",
    }
    registry = ModelRegistry(secrets=SecretsManager(env=env))
    registry.register_model("fast", None)
    registry.register_model("slow", None)
    router = ModelRouter(registry)

    selection_fast = router.select_model("fast")
    provider_fast = registry.get_provider_for_model("fast")
    assert selection_fast.provider_name == "http_json"
    assert isinstance(provider_fast, HTTPJsonProvider)

    selection_slow = router.select_model("slow")
    provider_slow = registry.get_provider_for_model("slow")
    assert selection_slow.provider_name == "dummy"
    assert isinstance(provider_slow, DummyProvider)
