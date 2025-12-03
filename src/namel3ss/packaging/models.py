"""
Packaging models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List


@dataclass
class AppBundle:
    app_name: str
    pages: List[str]
    flows: List[str]
    agents: List[str]
    plugins: List[str]
    models: List[str]
    metadata: dict[str, Any] = field(default_factory=dict)
