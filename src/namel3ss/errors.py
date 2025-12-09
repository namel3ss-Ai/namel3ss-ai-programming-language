"""
Custom error types for the Namel3ss V3 toolchain.
"""

from dataclasses import dataclass
from typing import Any, Optional


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


@dataclass
class ProviderConfigError(Namel3ssError):
    """Raised when provider configuration is missing or invalid."""

    code: str = "N3P-1801"
    diagnostics: list[dict[str, Any]] | None = None

    def __post_init__(self) -> None:  # pragma: no cover - trivial
        if self.diagnostics is None:
            self.diagnostics = [{"code": self.code, "message": self.message, "severity": "error"}]


@dataclass
class ProviderAuthError(Namel3ssError):
    """Raised when provider rejects credentials (401/403)."""

    code: str = "N3P-1802"
    diagnostics: list[dict[str, Any]] | None = None

    def __post_init__(self) -> None:  # pragma: no cover - trivial
        if self.diagnostics is None:
            self.diagnostics = [{"code": self.code, "message": self.message, "severity": "error"}]


@dataclass
class ProviderTimeoutError(Namel3ssError):
    """Raised when a provider call exceeds the configured timeout."""

    code: str = "N3P-1803"
    diagnostics: list[dict[str, Any]] | None = None

    def __post_init__(self) -> None:  # pragma: no cover - trivial
        if self.diagnostics is None:
            self.diagnostics = [{"code": self.code, "message": self.message, "severity": "error"}]


@dataclass
class ProviderRetryError(Namel3ssError):
    """Raised when a provider call exhausts retries."""

    attempts: int | None = None
    last_error: BaseException | None = None
    code: str = "N3P-1804"
    diagnostics: list[dict[str, Any]] | None = None

    def __post_init__(self) -> None:  # pragma: no cover - trivial
        if self.diagnostics is None:
            detail = f"last_error={self.last_error}" if self.last_error else "no last error"
            self.diagnostics = [
                {
                    "code": self.code,
                    "message": f"{self.message} ({detail})",
                    "severity": "error",
                }
            ]


@dataclass
class ProviderCircuitOpenError(Namel3ssError):
    """Raised when the provider circuit breaker is open."""

    code: str = "N3P-1805"
    diagnostics: list[dict[str, Any]] | None = None

    def __post_init__(self) -> None:  # pragma: no cover - trivial
        if self.diagnostics is None:
            self.diagnostics = [{"code": self.code, "message": self.message, "severity": "error"}]
