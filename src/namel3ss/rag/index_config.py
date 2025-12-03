from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class RAGIndexConfig:
    name: str
    backend: str = "memory"
    collection: str = "default"
    k: int = 10
    weight: float = 1.0
    enable_hybrid: bool = False
    dense_weight: float = 0.7
    sparse_weight: float = 0.3
    enable_rerank: bool = False
    enable_rewrite: bool = False
    dsn: Optional[str] = None
    options: Dict[str, Any] = field(default_factory=dict)
