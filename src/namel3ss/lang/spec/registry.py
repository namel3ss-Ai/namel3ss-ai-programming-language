from __future__ import annotations

from typing import Dict, Iterable, Optional

from .contracts import BlockContract, FieldSpec


def _req(name: str, field_type: str, description: str, allowed_values=None) -> FieldSpec:
    return FieldSpec(name=name, required=True, field_type=field_type, description=description, allowed_values=allowed_values)


def _opt(name: str, field_type: str, description: str, allowed_values=None) -> FieldSpec:
    return FieldSpec(name=name, required=False, field_type=field_type, description=description, allowed_values=allowed_values)


_CONTRACTS: Dict[str, BlockContract] = {
    "app": BlockContract(
        kind="app",
        description="Application entrypoint",
        required_fields=(
            _req("name", "string", "App identifier"),
            _req("entry_page", "string", "Entry page name"),
        ),
        optional_fields=(_opt("description", "string", "App description"),),
        allowed_children=("page",),
        unique_name_scope="app",
    ),
    "page": BlockContract(
        kind="page",
        description="Page definition",
        required_fields=(
            _req("name", "string", "Page identifier"),
            _req("route", "string", "Route path"),
        ),
        optional_fields=(
            _opt("title", "string", "Page title"),
            _opt("description", "string", "Page description"),
            _opt("properties", "mapping", "Arbitrary properties"),
            _opt("ai_calls", "list", "AI calls referenced"),
            _opt("agents", "list", "Agents referenced"),
            _opt("memories", "list", "Memories referenced"),
            _opt("sections", "list", "Sections for the page"),
            _opt("layout", "list", "Layout elements for the page"),
            _opt("ui_states", "list", "UI state declarations for the page"),
            _opt("styles", "list", "Style metadata for the page"),
        ),
        allowed_children=("section", "component"),
        unique_name_scope="page",
    ),
    "model": BlockContract(
        kind="model",
        description="Model declaration",
        required_fields=(
            _req("name", "string", "Model name"),
            _req("provider", "string", "Provider identifier"),
        ),
        optional_fields=(),
        allowed_children=(),
        unique_name_scope="model",
    ),
    "ai": BlockContract(
        kind="ai",
        description="AI call declaration",
        required_fields=(
            _req("name", "string", "AI call name"),
            _req("model_name", "string", "Model reference"),
            _req("input_source", "string", "Input source"),
        ),
        optional_fields=(
            _opt("description", "string", "AI call description"),
            _opt("memory_name", "string", "Memory reference"),
            _opt("system_prompt", "string", "System prompt"),
        ),
        allowed_children=(),
        unique_name_scope="ai",
    ),
    "agent": BlockContract(
        kind="agent",
        description="Agent definition",
        required_fields=(_req("name", "string", "Agent name"),),
        optional_fields=(
            _opt("goal", "string", "Agent goal"),
            _opt("personality", "string", "Personality hint"),
            _opt("memory_name", "string", "Memory reference"),
        ),
        allowed_children=(),
        unique_name_scope="agent",
    ),
    "flow": BlockContract(
        kind="flow",
        description="Flow definition",
        required_fields=(_req("name", "string", "Flow name"),),
        optional_fields=(
            _opt("description", "string", "Flow description"),
            _opt("steps", "list", "Flow steps"),
        ),
        allowed_children=(),
        unique_name_scope="flow",
    ),
    "memory": BlockContract(
        kind="memory",
        description="Memory space",
        required_fields=(
            _req("name", "string", "Memory name"),
            _req("memory_type", "string", "Memory type"),
        ),
        optional_fields=(
            _opt("retention", "string", "Retention hint"),
        ),
        allowed_children=(),
        unique_name_scope="memory",
    ),
    "plugin": BlockContract(
        kind="plugin",
        description="Plugin declaration",
        required_fields=(_req("name", "string", "Plugin name"),),
        optional_fields=(_opt("description", "string", "Plugin description"),),
        allowed_children=(),
        unique_name_scope="plugin",
    ),
    "section": BlockContract(
        kind="section",
        description="Page section",
        required_fields=(_req("name", "string", "Section name"),),
        optional_fields=(
            _opt("components", "list", "Components within the section"),
            _opt("layout", "list", "Nested layout elements within the section"),
            _opt("styles", "list", "Style metadata"),
        ),
        allowed_children=("component",),
        unique_name_scope="section",
    ),
    "component": BlockContract(
        kind="component",
        description="UI component",
        required_fields=(_req("type", "string", "Component type"),),
        optional_fields=(_opt("props", "mapping", "Component properties"),),
        allowed_children=(),
        unique_name_scope=None,
    ),
}


def get_contract(kind: str) -> Optional[BlockContract]:
    return _CONTRACTS.get(kind)


def all_contracts() -> Iterable[BlockContract]:
    return _CONTRACTS.values()
