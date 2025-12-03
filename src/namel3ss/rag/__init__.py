"""
RAG subsystem for Namel3ss V3.
"""

from .engine import RAGEngine
from .index_config import RAGIndexConfig
from .models import DocumentChunk
from .store import InMemoryVectorStore, embed_text
from .embeddings import EmbeddingProvider
from .embeddings_deterministic import DeterministicEmbeddingProvider
from .embeddings_http_json import HTTPJsonEmbeddingProvider
from .embeddings_openai import OpenAIEmbeddingProvider
from .embedding_registry import EmbeddingProviderRegistry

__all__ = [
    "RAGEngine",
    "RAGIndexConfig",
    "embed_text",
    "DocumentChunk",
    "InMemoryVectorStore",
    "EmbeddingProvider",
    "DeterministicEmbeddingProvider",
    "HTTPJsonEmbeddingProvider",
    "OpenAIEmbeddingProvider",
    "EmbeddingProviderRegistry",
]
