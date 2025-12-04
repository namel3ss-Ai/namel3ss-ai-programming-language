from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class RAGDocument:
    id: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    source: Optional[str] = None


@dataclass
class RetrievalResult:
    document: RAGDocument
    score: float
    rank: int
    metadata: Optional[Dict[str, Any]] = None
