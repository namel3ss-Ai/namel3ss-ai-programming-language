"""
Diagnostic subsystem.
"""

from .engine import DiagnosticEngine
from .models import Diagnostic as LegacyDiagnostic
from .structured import Diagnostic
from .registry import DiagnosticDefinition, get_definition, all_definitions, create_diagnostic
from .adapters import structured_to_legacy, legacy_to_structured

__all__ = [
    "DiagnosticEngine",
    "LegacyDiagnostic",
    "Diagnostic",
    "DiagnosticDefinition",
    "get_definition",
    "all_definitions",
    "create_diagnostic",
    "structured_to_legacy",
    "legacy_to_structured",
]
