from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

from .structured import Diagnostic


@dataclass(frozen=True)
class DiagnosticDefinition:
    code: str
    category: str
    default_severity: str
    message_template: str
    doc_url: Optional[str] = None


_DEFINITIONS: Dict[str, DiagnosticDefinition] = {
    # Syntax
    "N3-0001": DiagnosticDefinition(
        code="N3-0001",
        category="syntax",
        default_severity="error",
        message_template="Syntax error: {detail}",
    ),
    # Lang-spec / structural
    "N3-1001": DiagnosticDefinition(
        code="N3-1001",
        category="lang-spec",
        default_severity="error",
        message_template="Missing required field '{field}' on {kind}",
    ),
    "N3-1002": DiagnosticDefinition(
        code="N3-1002",
        category="lang-spec",
        default_severity="warning",
        message_template="Unknown field '{field}' on {kind}",
    ),
    "N3-1003": DiagnosticDefinition(
        code="N3-1003",
        category="lang-spec",
        default_severity="error",
        message_template="Invalid child block '{child}' under {parent}",
    ),
    "N3-1004": DiagnosticDefinition(
        code="N3-1004",
        category="lang-spec",
        default_severity="error",
        message_template="Duplicate name '{name}' in scope {scope}",
    ),
    "N3-1005": DiagnosticDefinition(
        code="N3-1005",
        category="lang-spec",
        default_severity="error",
        message_template="Field '{field}' on {kind} has invalid type or value",
    ),
    # Semantic
    "N3-2001": DiagnosticDefinition(
        code="N3-2001",
        category="semantic",
        default_severity="error",
        message_template="Reference to unknown '{target_kind}' named '{target}'",
    ),
    "N3-2002": DiagnosticDefinition(
        code="N3-2002",
        category="semantic",
        default_severity="error",
        message_template="Invalid argument or parameter binding in {context}",
    ),
    # Performance (reserved)
    "N3-3001": DiagnosticDefinition(
        code="N3-3001",
        category="performance",
        default_severity="warning",
        message_template="Potentially expensive chain detected",
    ),
    # Security (reserved)
    "N3-5001": DiagnosticDefinition(
        code="N3-5001",
        category="security",
        default_severity="warning",
        message_template="Insecure configuration detected",
    ),
}


def get_definition(code: str) -> Optional[DiagnosticDefinition]:
    return _DEFINITIONS.get(code)


def all_definitions() -> Iterable[DiagnosticDefinition]:
    return _DEFINITIONS.values()


def create_diagnostic(
    code: str,
    *,
    message_kwargs: Optional[Dict[str, Any]] = None,
    file: Optional[str] = None,
    line: Optional[int] = None,
    column: Optional[int] = None,
    end_line: Optional[int] = None,
    end_column: Optional[int] = None,
    hint: Optional[str] = None,
) -> Diagnostic:
    definition = get_definition(code)
    if not definition:
        raise ValueError(f"Unknown diagnostic code '{code}'")
    kwargs = message_kwargs or {}
    message = definition.message_template.format(**kwargs)
    return Diagnostic(
        code=definition.code,
        category=definition.category,
        severity=definition.default_severity,
        message=message,
        hint=hint,
        file=file,
        line=line,
        column=column,
        end_line=end_line,
        end_column=end_column,
        doc_url=definition.doc_url,
    )
