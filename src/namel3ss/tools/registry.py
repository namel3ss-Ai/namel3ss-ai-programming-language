"""
Registry for tools.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Dict, List, Optional


@dataclass
class ToolConfig:
    name: str
    kind: str
    method: str
    url_template: str
    headers: dict
    body_template: object | None = None


@dataclass
class AiToolSpec:
    name: str
    description: Optional[str]
    parameters: dict


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, ToolConfig] = {}

    def register(self, tool: ToolConfig) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[ToolConfig]:
        return self._tools.get(name)

    @property
    def tools(self) -> Dict[str, ToolConfig]:
        """Expose registered tools for inspection/testing."""
        return self._tools

    def list_names(self) -> List[str]:
        return list(self._tools.keys())

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)


_PLACEHOLDER_RE = re.compile(r"{([^{}]+)}")


def build_ai_tool_specs(tool_names: List[str], tool_registry: ToolRegistry) -> List[AiToolSpec]:
    """
    Build provider-neutral tool specs for AI function/tool-calling.

    Parameters are derived from placeholders in url_template; all are treated as string.
    """
    specs: List[AiToolSpec] = []
    for tool_name in tool_names:
        tool = tool_registry.get(tool_name)
        if tool is None:
            raise ValueError(f"Unknown tool '{tool_name}'")
        placeholders = _PLACEHOLDER_RE.findall(tool.url_template or "")
        properties = {name: {"type": "string"} for name in placeholders}
        required = list(dict.fromkeys(placeholders))
        parameters = {
            "type": "object",
            "properties": properties,
            "required": required,
        }
        specs.append(
            AiToolSpec(
                name=tool.name,
                description=f"Tool {tool.name} ({tool.kind})",
                parameters=parameters,
            )
        )
    return specs
