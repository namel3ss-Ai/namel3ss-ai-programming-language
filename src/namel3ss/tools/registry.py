"""
Registry for tools.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .models import Tool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def list_names(self) -> List[str]:
        return list(self._tools.keys())
