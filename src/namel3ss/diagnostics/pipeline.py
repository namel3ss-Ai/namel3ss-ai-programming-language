"""
Diagnostic pipeline helpers.
"""

from __future__ import annotations

from typing import List, Optional

from .engine import DiagnosticEngine
from .models import Diagnostic
from ..lang.validator import validate_module


def run_diagnostics(ir_program, available_plugins: Optional[set[str]] = None) -> List[Diagnostic]:
    diags: List[Diagnostic] = []
    diags.extend(validate_module(ir_program))
    diags.extend(DiagnosticEngine().analyze_ir(ir_program, available_plugins=available_plugins))
    return diags
