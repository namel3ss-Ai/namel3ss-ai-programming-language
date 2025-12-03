"""
IR validator driven by language contracts.
"""

from __future__ import annotations

from typing import List, Optional

from .spec import BlockKind, LANG_SPEC
from ..diagnostics.models import Diagnostic
from ..ir import IRFlow, IRPage, IRProgram


def _diag(code: str, severity: str, category: str, message: str, location: Optional[str], hint: Optional[str] = None):
    return Diagnostic(
        code=code,
        severity=severity,
        category=category,
        message=message,
        location=location,
        hint=hint,
    )


def _require_fields(obj, fields: list[str], kind: BlockKind, location_prefix: str, category: str) -> List[Diagnostic]:
    diags: List[Diagnostic] = []
    for field in fields:
        value = getattr(obj, field, None)
        if value is None or (isinstance(value, str) and value == ""):
            diags.append(
                _diag(
                    code="N3-LANG-010",
                    severity="error",
                    category=category,
                    message=f"Missing required field '{field}'",
                    location=f"{location_prefix}:{getattr(obj, 'name', '')}",
                    hint=f"Specify '{field}' for {kind.value}.",
                )
            )
    return diags


def validate_module(ir_program: IRProgram) -> List[Diagnostic]:
    diagnostics: List[Diagnostic] = []

    # Apps
    for app in ir_program.apps.values():
        diagnostics.extend(
            _require_fields(
                app,
                list(LANG_SPEC[BlockKind.APP].required_fields),
                BlockKind.APP,
                "app",
                "lang-spec",
            )
        )

    # Models
    for model in ir_program.models.values():
        diagnostics.extend(
            _require_fields(
                model,
                list(LANG_SPEC[BlockKind.MODEL].required_fields),
                BlockKind.MODEL,
                "model",
                "lang-spec",
            )
        )

    # AI calls
    for ai_call in ir_program.ai_calls.values():
        diagnostics.extend(
            _require_fields(
                ai_call,
                list(LANG_SPEC[BlockKind.AI].required_fields),
                BlockKind.AI,
                "ai",
                "lang-spec",
            )
        )
        if ai_call.model_name and ai_call.model_name not in ir_program.models:
            diagnostics.append(
                _diag(
                    code="N3-SEM-010",
                    severity="error",
                    category="semantic",
                    message=f"AI call references unknown model '{ai_call.model_name}'",
                    location=f"ai:{ai_call.name}",
                    hint="Declare the model or fix the reference.",
                )
            )

    # Pages
    for page in ir_program.pages.values():
        diagnostics.extend(
            _require_fields(
                page,
                list(LANG_SPEC[BlockKind.PAGE].required_fields),
                BlockKind.PAGE,
                "page",
                "lang-spec",
            )
        )
        for ai_name in page.ai_calls:
            if ai_name not in ir_program.ai_calls:
                diagnostics.append(
                    _diag(
                        code="N3-SEM-011",
                        severity="error",
                        category="semantic",
                        message=f"Page references unknown ai call '{ai_name}'",
                        location=f"page:{page.name}",
                        hint="Declare the ai call or fix the reference.",
                    )
                )
        for agent_name in page.agents:
            if agent_name not in ir_program.agents:
                diagnostics.append(
                    _diag(
                        code="N3-SEM-012",
                        severity="error",
                        category="semantic",
                        message=f"Page references unknown agent '{agent_name}'",
                        location=f"page:{page.name}",
                        hint="Declare the agent or fix the reference.",
                    )
                )
        for memory_name in page.memories:
            if memory_name not in ir_program.memories:
                diagnostics.append(
                    _diag(
                        code="N3-SEM-013",
                        severity="error",
                        category="semantic",
                        message=f"Page references unknown memory '{memory_name}'",
                        location=f"page:{page.name}",
                        hint="Declare the memory or fix the reference.",
                    )
                )
        for section in page.sections:
            diagnostics.extend(
                _require_fields(
                    section,
                    list(LANG_SPEC[BlockKind.SECTION].required_fields),
                    BlockKind.SECTION,
                    f"page:{page.name}/section",
                    "lang-spec",
                )
            )
            for comp in section.components:
                diagnostics.extend(
                    _require_fields(
                        comp,
                        list(LANG_SPEC[BlockKind.COMPONENT].required_fields),
                        BlockKind.COMPONENT,
                        f"page:{page.name}/component",
                        "lang-spec",
                    )
                )

    # Agents
    for agent in ir_program.agents.values():
        diagnostics.extend(
            _require_fields(
                agent,
                list(LANG_SPEC[BlockKind.AGENT].required_fields),
                BlockKind.AGENT,
                "agent",
                "lang-spec",
            )
        )

    # Flows
    for flow in ir_program.flows.values():
        diagnostics.extend(
            _require_fields(
                flow,
                list(LANG_SPEC[BlockKind.FLOW].required_fields),
                BlockKind.FLOW,
                "flow",
                "lang-spec",
            )
        )
        _validate_flow_steps(flow, ir_program, diagnostics)

    # Memory
    for mem in ir_program.memories.values():
        diagnostics.extend(
            _require_fields(
                mem,
                list(LANG_SPEC[BlockKind.MEMORY].required_fields),
                BlockKind.MEMORY,
                "memory",
                "lang-spec",
            )
        )
        if mem.memory_type and mem.memory_type not in {"conversation", "user", "global"}:
            diagnostics.append(
                _diag(
                    code="N3-LANG-014",
                    severity="error",
                    category="lang-spec",
                    message=f"Unsupported memory type '{mem.memory_type}'",
                    location=f"memory:{mem.name}",
                    hint="Use one of: conversation, user, global.",
                )
            )

    # Plugins
    for plugin in ir_program.plugins.values():
        diagnostics.extend(
            _require_fields(
                plugin,
                list(LANG_SPEC[BlockKind.PLUGIN].required_fields),
                BlockKind.PLUGIN,
                "plugin",
                "lang-spec",
            )
        )

    # App entry pages must exist
    for app in ir_program.apps.values():
        if app.entry_page and app.entry_page not in ir_program.pages:
            diagnostics.append(
                _diag(
                    code="N3-SEM-014",
                    severity="error",
                    category="semantic",
                    message=f"App entry_page '{app.entry_page}' not found",
                    location=f"app:{app.name}",
                    hint="Declare the page or update entry_page.",
                )
            )

    return diagnostics


def _validate_flow_steps(flow: IRFlow, ir_program: IRProgram, diagnostics: List[Diagnostic]) -> None:
    if not flow.steps:
        diagnostics.append(
            _diag(
                code="N3-LANG-002",
                severity="warning",
                category="lang-spec",
                message="Flow has no steps",
                location=f"flow:{flow.name}",
                hint="Add at least one step to the flow.",
            )
        )
        return
    for step in flow.steps:
        if not step.target:
            diagnostics.append(
                _diag(
                    code="N3-LANG-012",
                    severity="error",
                    category="lang-spec",
                    message="Flow step missing target",
                    location=f"flow:{flow.name}/step:{step.name}",
                    hint="Set target to an ai/agent/tool name.",
                )
            )
        if step.kind == "ai" and step.target not in ir_program.ai_calls:
            diagnostics.append(
                _diag(
                    code="N3-SEM-020",
                    severity="error",
                    category="semantic",
                    message=f"Flow step references unknown ai '{step.target}'",
                    location=f"flow:{flow.name}/step:{step.name}",
                    hint="Declare the ai call or fix the reference.",
                )
            )
        if step.kind == "agent" and step.target not in ir_program.agents:
            diagnostics.append(
                _diag(
                    code="N3-SEM-021",
                    severity="error",
                    category="semantic",
                    message=f"Flow step references unknown agent '{step.target}'",
                    location=f"flow:{flow.name}/step:{step.name}",
                    hint="Declare the agent or fix the reference.",
                )
            )
