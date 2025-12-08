"""
Registry for tools.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Sequence


@dataclass
class ToolConfig:
    name: str
    kind: str
    method: str
    url_expr: object | None = None
    url_template: str | None = None
    headers: dict = field(default_factory=dict)
    query_params: dict = field(default_factory=dict)
    body_fields: dict = field(default_factory=dict)
    body_template: object | None = None
    input_fields: list[str] = field(default_factory=list)


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


def build_ai_tool_specs(tool_refs: Sequence[Any], tool_registry: ToolRegistry) -> List[AiToolSpec]:
    """
    Build provider-neutral tool specs for AI function/tool-calling.

    Parameters are derived from placeholders in url_template; all are treated as string.
    """
    specs: List[AiToolSpec] = []
    for ref in tool_refs:
        if isinstance(ref, str):
            internal_name = ref
            exposed_name = ref
        else:
            internal_name = getattr(ref, "internal_name", None) or getattr(ref, "name", None)
            exposed_name = getattr(ref, "exposed_name", None) or internal_name
        if not internal_name:
            continue
        tool = tool_registry.get(internal_name)
        if tool is None:
            raise ValueError(f"Unknown tool '{internal_name}'")
        input_fields = list(getattr(tool, "input_fields", []) or [])
        if not input_fields:
            placeholders = _PLACEHOLDER_RE.findall(getattr(tool, "url_template", "") or "")
            input_fields = list(dict.fromkeys(placeholders))
        properties = {name: {"type": "string"} for name in input_fields}
        parameters = {
            "type": "object",
            "properties": properties,
            "required": list(dict.fromkeys(input_fields)),
        }
        specs.append(
            AiToolSpec(
                name=exposed_name,
                description=f"Tool {tool.name} ({tool.kind})",
                parameters=parameters,
            )
        )
    return specs
