from __future__ import annotations

from dataclasses import fields, is_dataclass
from typing import Any, Iterable, List, Optional

from ...diagnostics import create_diagnostic, structured_to_legacy
from ...diagnostics.models import Diagnostic
from ...ir import (
    IRMemory,
    IRPage,
    IRProgram,
)
from .registry import get_contract


def _diag(code: str, severity: str, message: str, location: Optional[str], hint: Optional[str] = None, category: str = "lang-spec"):
    # Legacy helper retained for compatibility in a few semantic checks that do
    # not yet use the V3 registry.
    return Diagnostic(code=code, severity=severity, category=category, message=message, location=location, hint=hint)


def _field_names(obj: Any) -> Iterable[str]:
    if is_dataclass(obj):
        dataclass_fields = {f.name for f in fields(obj)}
        dynamic_fields = set(getattr(obj, "__dict__", {}).keys())
        return dataclass_fields | dynamic_fields
    return obj.__dict__.keys()


def _matches_type(value: Any, field_type: str) -> bool:
    if field_type in {"string", "identifier"}:
        return isinstance(value, str)
    if field_type == "bool":
        return isinstance(value, bool)
    if field_type == "int":
        return isinstance(value, int)
    if field_type == "list":
        return isinstance(value, list)
    if field_type == "mapping":
        return isinstance(value, dict)
    return True


def _validate_fields(obj: Any, kind: str, location: str) -> List[Diagnostic]:
    diags: List[Diagnostic] = []
    contract = get_contract(kind)
    if not contract:
        v3 = create_diagnostic(
            "N3-1002",
            message_kwargs={"field": "contract", "kind": kind},
            file=location,
            hint=f"Register a contract for kind '{kind}'.",
        )
        diags.append(structured_to_legacy(v3))
        return diags
    all_fields = contract.all_field_names()
    for field_spec in contract.required_fields:
        value = getattr(obj, field_spec.name, None)
        if value is None or (isinstance(value, str) and value == ""):
            v3 = create_diagnostic(
                "N3-1001",
                message_kwargs={"field": field_spec.name, "kind": kind},
                file=location,
                hint=f"Specify '{field_spec.name}' for {kind}.",
            )
            diags.append(structured_to_legacy(v3))
        elif not _matches_type(value, field_spec.field_type):
            v3 = create_diagnostic(
                "N3-1005",
                message_kwargs={"field": field_spec.name, "kind": kind},
                file=location,
                hint=f"Expected {field_spec.field_type}.",
            )
            diags.append(structured_to_legacy(v3))
        elif field_spec.allowed_values and value not in field_spec.allowed_values:
            v3 = create_diagnostic(
                "N3-1005",
                message_kwargs={"field": field_spec.name, "kind": kind},
                file=location,
                hint=f"Allowed values: {sorted(field_spec.allowed_values)}",
            )
            diags.append(structured_to_legacy(v3))
    for fname in _field_names(obj):
        if fname.startswith("_"):
            continue
        if fname not in all_fields and fname not in contract.allowed_children:
            v3 = create_diagnostic(
                "N3-1002",
                message_kwargs={"field": fname, "kind": kind},
                file=location,
                hint="Remove or rename the field.",
            )
            diags.append(structured_to_legacy(v3))
    return diags


def _validate_children(page: IRPage, diags: List[Diagnostic]) -> None:
    names = [s.name for s in page.sections]
    if len(names) != len(set(names)):
        v3 = create_diagnostic(
            "N3-1004",
            message_kwargs={"name": "section", "scope": f"page:{page.name}"},
            file=f"page:{page.name}",
            hint="Ensure section names are unique within a page.",
        )
        diags.append(structured_to_legacy(v3))
    for section in page.sections:
        diags.extend(_validate_fields(section, "section", f"page:{page.name}/section:{section.name}"))
        for comp in section.components:
            diags.extend(_validate_fields(comp, "component", f"page:{page.name}/component"))


def _validate_memory(mem: IRMemory, diags: List[Diagnostic]) -> None:
    allowed = {"conversation", "user", "global"}
    if mem.memory_type and mem.memory_type not in allowed:
        v3 = create_diagnostic(
            "N3-1005",
            message_kwargs={"field": "memory_type", "kind": "memory"},
            file=f"memory:{mem.name}",
            hint="Use one of: conversation, user, global.",
        )
        diags.append(structured_to_legacy(v3))


def validate_ir(ir_program: IRProgram) -> List[Diagnostic]:
    diags: List[Diagnostic] = []
    for app in ir_program.apps.values():
        diags.extend(_validate_fields(app, "app", f"app:{app.name}"))
    for page in ir_program.pages.values():
        diags.extend(_validate_fields(page, "page", f"page:{page.name}"))
        _validate_children(page, diags)
    for model in ir_program.models.values():
        diags.extend(_validate_fields(model, "model", f"model:{model.name}"))
    for ai_call in ir_program.ai_calls.values():
        diags.extend(_validate_fields(ai_call, "ai", f"ai:{ai_call.name}"))
    for agent in ir_program.agents.values():
        diags.extend(_validate_fields(agent, "agent", f"agent:{agent.name}"))
    for flow in ir_program.flows.values():
        diags.extend(_validate_fields(flow, "flow", f"flow:{flow.name}"))
    for mem in ir_program.memories.values():
        diags.extend(_validate_fields(mem, "memory", f"memory:{mem.name}"))
        _validate_memory(mem, diags)
    for plugin in ir_program.plugins.values():
        diags.extend(_validate_fields(plugin, "plugin", f"plugin:{plugin.name}"))
    return diags
