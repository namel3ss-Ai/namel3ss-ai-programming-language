"""
Custom error types for the Namel3ss V3 toolchain.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Namel3ssError(Exception):
    """Base error with optional location metadata."""

    message: str
    line: Optional[int] = None
    column: Optional[int] = None

    def __str__(self) -> str:  # pragma: no cover - trivial
        location = ""
        if self.line is not None:
            location = f" (line {self.line}"
            if self.column is not None:
                location += f", column {self.column}"
            location += ")"
        return f"{self.message}{location}"


class LexError(Namel3ssError):
    """Lexical analysis error."""


class ParseError(Namel3ssError):
    """Parsing error."""


class IRError(Namel3ssError):
    """Intermediate representation transformation error."""
