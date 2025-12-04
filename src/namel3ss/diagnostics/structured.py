from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class Diagnostic:
    code: str
    category: str  # "syntax" | "semantic" | "lang-spec" | "performance" | "security"
    severity: str  # "info" | "warning" | "error"
    message: str
    hint: Optional[str]
    file: Optional[str]
    line: Optional[int]
    column: Optional[int]
    end_line: Optional[int] = None
    end_column: Optional[int] = None
    doc_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "category": self.category,
            "severity": self.severity,
            "message": self.message,
            "hint": self.hint,
            "file": self.file,
            "line": self.line,
            "column": self.column,
            "end_line": self.end_line,
            "end_column": self.end_column,
            "doc_url": self.doc_url,
        }
