from namel3ss.rag.embedding_registry import EmbeddingProviderRegistry
from namel3ss.rag.embeddings_deterministic import DeterministicEmbeddingProvider
from namel3ss.rag.embeddings_http_json import HTTPJsonEmbeddingProvider
from namel3ss.rag.embeddings_openai import OpenAIEmbeddingProvider
from namel3ss.secrets.manager import SecretsManager


def test_registry_defaults_to_deterministic():
    registry = EmbeddingProviderRegistry(secrets=SecretsManager(env={}))
    provider = registry.get_default_provider()
    assert isinstance(provider, DeterministicEmbeddingProvider)


def test_registry_builds_openai_provider():
    env = {"OPENAI_API_KEY": "sk-test", "N3_EMBEDDINGS_PROVIDER": "openai", "N3_EMBEDDINGS_MODEL": "text-embedding-3-small"}
    registry = EmbeddingProviderRegistry(secrets=SecretsManager(env=env))
    provider = registry.get_default_provider()
    assert isinstance(provider, OpenAIEmbeddingProvider)


def test_registry_builds_http_provider():
    env = {
        "N3_EMBEDDINGS_PROVIDER": "http_json",
        "N3_EMBEDDINGS_BASE_URL": "http://localhost/api/emb",
        "N3_EMBEDDINGS_RESPONSE_PATH": "data.embedding",
    }
    registry = EmbeddingProviderRegistry(secrets=SecretsManager(env=env))
    provider = registry.get_default_provider()
    assert isinstance(provider, HTTPJsonEmbeddingProvider)
