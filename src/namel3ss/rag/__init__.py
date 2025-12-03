"""
RAG subsystem for Namel3ss V3.
"""

from .engine import RAGEngine, embed_text
from .models import DocumentChunk
from .store import InMemoryVectorStore

__all__ = ["RAGEngine", "embed_text", "DocumentChunk", "InMemoryVectorStore"]
