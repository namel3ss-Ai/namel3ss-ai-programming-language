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
from .graph import GraphEngine

__all__ = [
    "RAGEngine",
    "GraphEngine",
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
