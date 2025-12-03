"""
Diagnostic models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional


@dataclass
class Diagnostic:
    code: str = "N3-0000"
    severity: Literal["error", "warning", "info"] = "info"
    category: str = "general"
    message: str = ""
    location: Optional[str] = None
    hint: Optional[str] = None
    auto_fix: Optional[dict[str, Any]] = None
    # Backward compatibility with previous `level` naming.
    level: Optional[Literal["error", "warning", "info"]] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.level:
            self.severity = self.level
        else:
            self.level = self.severity

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "category": self.category,
            "message": self.message,
            "location": self.location,
            "hint": self.hint,
            "auto_fix": self.auto_fix,
        }


def has_effective_errors(diagnostics: list[Diagnostic], strict: bool = False) -> bool:
    for diag in diagnostics:
        sev = diag.severity or diag.level or "info"
        if sev == "error":
            return True
        if strict and sev == "warning":
            return True
    return False
