"""
Registry for tools.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Sequence

from ..errors import Namel3ssError

@dataclass
class ToolConfig:
    name: str
    kind: str
    method: str | None
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

    Parameters are derived from url placeholders, input references, and request field names.
    """
    specs: List[AiToolSpec] = []

    def _collect_names(tool: ToolConfig) -> list[str]:
        names: list[str] = []

        def _add(name: str) -> None:
            if not name:
                return
            if name not in names:
                names.append(name)

        for name in getattr(tool, "input_fields", []) or []:
            _add(name)
        for placeholder in _PLACEHOLDER_RE.findall(getattr(tool, "url_template", "") or ""):
            _add(placeholder)
        for mapping in (getattr(tool, "query_params", {}) or {}, getattr(tool, "body_fields", {}) or {}, getattr(tool, "headers", {}) or {}):
            for key in mapping.keys():
                _add(str(key))
        body_template = getattr(tool, "body_template", None)
        if isinstance(body_template, str):
            for placeholder in _PLACEHOLDER_RE.findall(body_template):
                _add(placeholder)
        return names

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
            raise Namel3ssError(f"AI tool '{internal_name}' is not declared or registered.")
        param_names = _collect_names(tool)
        properties = {name: {"type": "string"} for name in param_names}
        parameters = {
            "type": "object",
            "properties": properties,
            "required": list(dict.fromkeys(getattr(tool, "input_fields", []) or param_names)),
        }
        specs.append(
            AiToolSpec(
                name=exposed_name,
                description=f"Tool {tool.name} ({tool.kind})",
                parameters=parameters,
            )
        )
    return specs
