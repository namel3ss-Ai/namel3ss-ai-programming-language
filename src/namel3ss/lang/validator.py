"""
IR validator driven by language contracts.
"""

from __future__ import annotations

from typing import List, Optional

from ..diagnostics import create_diagnostic, structured_to_legacy
from ..diagnostics.models import Diagnostic
from ..ir import IRFlow, IRProgram
from .spec.validator import validate_ir as validate_contracts


def _diag(code: str, severity: str, category: str, message: str, location: Optional[str], hint: Optional[str] = None):
    return Diagnostic(
        code=code,
        severity=severity,
        category=category,
        message=message,
        location=location,
        hint=hint,
    )


def validate_module(ir_program: IRProgram) -> List[Diagnostic]:
    diagnostics: List[Diagnostic] = []

    # Contract-driven checks
    diagnostics.extend(validate_contracts(ir_program))

    # Semantic references
    for ai_call in ir_program.ai_calls.values():
        if ai_call.model_name and ai_call.model_name not in ir_program.models:
            v3 = create_diagnostic(
                "N3-2001",
                message_kwargs={"target_kind": "model", "target": ai_call.model_name},
                file=f"ai:{ai_call.name}",
                hint="Declare the model or fix the reference.",
            )
            diagnostics.append(structured_to_legacy(v3))

    for page in ir_program.pages.values():
        for ai_name in page.ai_calls:
            if ai_name not in ir_program.ai_calls:
                v3 = create_diagnostic(
                    "N3-2001",
                    message_kwargs={"target_kind": "ai", "target": ai_name},
                    file=f"page:{page.name}",
                    hint="Declare the ai call or fix the reference.",
                )
                diagnostics.append(structured_to_legacy(v3))
        for agent_name in page.agents:
            if agent_name not in ir_program.agents:
                v3 = create_diagnostic(
                    "N3-2001",
                    message_kwargs={"target_kind": "agent", "target": agent_name},
                    file=f"page:{page.name}",
                    hint="Declare the agent or fix the reference.",
                )
                diagnostics.append(structured_to_legacy(v3))
        for memory_name in page.memories:
            if memory_name not in ir_program.memories:
                v3 = create_diagnostic(
                    "N3-2001",
                    message_kwargs={"target_kind": "memory", "target": memory_name},
                    file=f"page:{page.name}",
                    hint="Declare the memory or fix the reference.",
                )
                diagnostics.append(structured_to_legacy(v3))

    for flow in ir_program.flows.values():
        _validate_flow_steps(flow, ir_program, diagnostics)

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
