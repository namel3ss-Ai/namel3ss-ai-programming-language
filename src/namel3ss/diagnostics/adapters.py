from __future__ import annotations

from typing import Any, Optional

from .models import Diagnostic as LegacyDiagnostic
from .structured import Diagnostic


def structured_to_legacy(diag: Diagnostic) -> LegacyDiagnostic:
    """
    Convert a structured Diagnostic into the legacy Diagnostic structure used
    across the existing codebase. Line/column information is not represented in
    the legacy model, so the `location` field will be derived from the file and
    position when available.
    """
    location = _format_location(diag.file, diag.line, diag.column)
    return LegacyDiagnostic(
        code=diag.code,
        severity=diag.severity,
        category=diag.category,
        message=diag.message,
        location=location,
        hint=diag.hint,
    )


def legacy_to_structured(legacy_diag: Any) -> Diagnostic:
    """
    Convert a legacy Diagnostic object into a structured Diagnostic. Location is
    mapped to the `file` field when available; line/column are left unset because the
    legacy model does not track them explicitly.
    """
    file = getattr(legacy_diag, "location", None)
    return Diagnostic(
        code=getattr(legacy_diag, "code", "N3-0000"),
        category=getattr(legacy_diag, "category", "general"),
        severity=getattr(legacy_diag, "severity", getattr(legacy_diag, "level", "info")),
        message=getattr(legacy_diag, "message", ""),
        hint=getattr(legacy_diag, "hint", None),
        file=file,
        line=None,
        column=None,
    )


def _format_location(file: Optional[str], line: Optional[int], column: Optional[int]) -> Optional[str]:
    if file and line and column:
        return f"{file}:{line}:{column}"
    if file and line:
        return f"{file}:{line}"
    return file
