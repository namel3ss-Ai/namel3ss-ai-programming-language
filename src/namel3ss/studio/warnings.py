"""
Best-practices warning collection for Studio.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, List

from .. import ir


@dataclass
class StudioWarning:
    code: str
    message: str
    details: str | None
    entity_kind: str
    entity_name: str
    level: str = "warning"
    file: str | None = None

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def _flow_warnings(flow: ir.IRFlow) -> List[StudioWarning]:
    warnings: List[StudioWarning] = []
    steps = list(ir._yield_flow_steps(flow.steps))
    uses_external = any(getattr(step, "kind", "") in {"ai", "agent", "tool"} for step in steps)
    if uses_external and not flow.error_steps:
        warnings.append(
            StudioWarning(
                code="N3-BP-1001",
                message=f"Flow '{flow.name}' has no error handling.",
                details="Consider adding error_steps to handle AI/tool failures gracefully.",
                entity_kind="flow",
                entity_name=flow.name,
            )
        )
    if len(steps) >= 6 and not any(getattr(step, "message", None) for step in steps):
        warnings.append(
            StudioWarning(
                code="N3-BP-1002",
                message=f"Flow '{flow.name}' has many steps but no notes/log messages.",
                details="Add brief messages or logging to make long flows easier to debug.",
                entity_kind="flow",
                entity_name=flow.name,
                level="info",
            )
        )
    return warnings


def _tool_warnings(tool: ir.IRTool) -> List[StudioWarning]:
    warnings: List[StudioWarning] = []
    url_val = ""
    if hasattr(tool, "url_template") and tool.url_template:
        url_val = str(tool.url_template)
    elif getattr(tool, "url_expr", None) is not None:
        expr = getattr(tool, "url_expr")
        url_val = str(getattr(expr, "value", "") or "")
    url = (url_val or "").lower()
    if url.startswith("http") and tool.auth is None:
        warnings.append(
            StudioWarning(
                code="N3-BP-2001",
                message=f"Tool '{tool.name}' has no auth configured.",
                details="Configure auth for external HTTP tools to avoid rejected requests.",
                entity_kind="tool",
                entity_name=tool.name,
            )
        )
    if tool.timeout_seconds is None:
        warnings.append(
            StudioWarning(
                code="N3-BP-2002",
                message=f"Tool '{tool.name}' has no timeout.",
                details="Set timeout_seconds to prevent hanging tool calls.",
                entity_kind="tool",
                entity_name=tool.name,
                level="info",
            )
        )
    return warnings


def _rag_warnings(pipeline: ir.IRRagPipeline) -> List[StudioWarning]:
    warnings: List[StudioWarning] = []
    stage_types = [s.type for s in pipeline.stages if hasattr(s, "type")]
    has_vector = any("vector" in (t or "") for t in stage_types)
    has_rerank = any((t or "") == "rerank" for t in stage_types)
    has_answer = any((t or "") == "answer" for t in stage_types)
    if has_vector and not has_rerank:
        warnings.append(
            StudioWarning(
                code="N3-BP-3001",
                message=f"RAG pipeline '{pipeline.name}' has retrieval but no rerank stage.",
                details="Add a rerank stage to improve result quality when combining vector sources.",
                entity_kind="rag",
                entity_name=pipeline.name,
            )
        )
    if not has_answer:
        warnings.append(
            StudioWarning(
                code="N3-BP-3002",
                message=f"RAG pipeline '{pipeline.name}' has no answer stage.",
                details="Add an answer/generation stage so RAG results produce a response.",
                entity_kind="rag",
                entity_name=pipeline.name,
            )
        )
    return warnings


def _memory_warnings(program: ir.IRProgram) -> List[StudioWarning]:
    warnings: List[StudioWarning] = []
    declared = set((program.memories or {}).keys())
    used = set()
    for ai in (program.ai_calls or {}).values():
        if getattr(ai, "memory_name", None):
            used.add(ai.memory_name)
    unused = declared - used
    for name in sorted(unused):
        warnings.append(
            StudioWarning(
                code="N3-BP-4001",
                message=f"Memory '{name}' is declared but not referenced by any AI.",
                details="Bind this memory to an AI or remove it if unused.",
                entity_kind="memory",
                entity_name=name,
                level="info",
            )
        )
    return warnings


def collect_warnings(program: ir.IRProgram) -> List[Dict[str, object]]:
    warnings: List[StudioWarning] = []
    for flow in (program.flows or {}).values():
        warnings.extend(_flow_warnings(flow))
    for tool in (program.tools or {}).values():
        warnings.extend(_tool_warnings(tool))
    for pipeline in (program.rag_pipelines or {}).values():
        warnings.extend(_rag_warnings(pipeline))
    warnings.extend(_memory_warnings(program))
    return [w.to_dict() for w in warnings]
