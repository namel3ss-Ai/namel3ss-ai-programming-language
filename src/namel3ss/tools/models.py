"""
Tool models and protocols.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class ToolDefinition:
    name: str
    description: str
    params_schema: dict[str, Any] | None = None


class Tool(Protocol):
    name: str

    def run(self, **kwargs: Any) -> Any:
        ...
