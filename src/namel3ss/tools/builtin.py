"""
Built-in tools for Namel3ss.
"""

from __future__ import annotations

from typing import Any

from .models import Tool
from .registry import ToolRegistry


BUILTIN_TOOL_NAMES = ["echo", "add_numbers"]


class EchoTool:
    name = "echo"

    def run(self, **kwargs: Any) -> str:
        message = kwargs.get("message", "")
        return f"echo:{message}"


class AddNumbersTool:
    name = "add_numbers"

    def run(self, **kwargs: Any) -> int:
        a = kwargs.get("a", 0)
        b = kwargs.get("b", 0)
        return int(a) + int(b)


def register_builtin_tools(registry: ToolRegistry) -> ToolRegistry:
    registry.register(EchoTool())
    registry.register(AddNumbersTool())
    return registry


def is_builtin_tool(name: str) -> bool:
    return name in BUILTIN_TOOL_NAMES
