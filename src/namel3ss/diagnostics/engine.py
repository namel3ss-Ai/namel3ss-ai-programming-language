"""
Diagnostic engine for IR validation.
"""

from __future__ import annotations

from typing import List, Optional

from .models import Diagnostic


class DiagnosticEngine:
    def analyze_ir(self, ir_program, available_plugins: Optional[set[str]] = None) -> List[Diagnostic]:
        diagnostics: List[Diagnostic] = []

        # Pages without routes
        for page_name, page in ir_program.pages.items():
            if not page.route:
                diagnostics.append(
                    Diagnostic(
                        code="N3-LANG-001",
                        severity="warning",
                        category="lang-spec",
                        message="Page has no route",
                        location=f"page:{page_name}",
                        hint="Add `route \"...\"` to the page block.",
                    )
                )

        # Flows without steps
        for flow_name, flow in ir_program.flows.items():
            if not flow.steps:
                diagnostics.append(
                    Diagnostic(
                        code="N3-LANG-002",
                        severity="warning",
                        category="lang-spec",
                        message="Flow has no steps",
                        location=f"flow:{flow_name}",
                        hint="Add at least one step under the flow.",
                    )
                )

        # Agents unused (not referenced in pages or flows)
        referenced_agents = set()
        for page in ir_program.pages.values():
            referenced_agents.update(page.agents)
        for flow in ir_program.flows.values():
            for step in flow.steps:
                if step.kind == "agent":
                    referenced_agents.add(step.target)
        for agent_name in ir_program.agents.keys():
            if agent_name not in referenced_agents:
                diagnostics.append(
                    Diagnostic(
                        code="N3-SEM-001",
                        severity="warning",
                        category="semantic",
                        message="Agent declared but not referenced",
                        location=f"agent:{agent_name}",
                        hint="Reference the agent from a page or flow, or remove it.",
                    )
                )

        # Plugin availability check
        if available_plugins is not None:
            for plugin_name in ir_program.plugins.keys():
                if plugin_name not in available_plugins:
                    diagnostics.append(
                        Diagnostic(
                            code="N3-LANG-003",
                            severity="error",
                            category="lang-spec",
                            message="Plugin declared but not available",
                            location=f"plugin:{plugin_name}",
                            hint="Ensure the plugin is installed/enabled in the runtime environment.",
                        )
                    )

        # RAG documents check
        if hasattr(ir_program, "rag_documents") and ir_program.rag_documents == 0:
            diagnostics.append(
                Diagnostic(
                    code="N3-INFO-001",
                    severity="info",
                    category="runtime",
                    message="No RAG documents indexed",
                    location=None,
                    hint="Index documents via RAG engine or sync worker to enable retrieval.",
                )
            )

        return diagnostics
