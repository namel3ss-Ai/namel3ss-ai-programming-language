"""
Transitional parser facade.

Delegates to the legacy monolithic parser while a modular split is built.
Public API remains `parse` and `ParseError`.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from .errors import ParseError

# Load the legacy monolithic parser module under a private name to avoid
# circular imports with this package facade.
_LEGACY_NAME = "namel3ss._parser_legacy"
_LEGACY_PATH = Path(__file__).resolve().parents[1] / "parser.py"
if _LEGACY_NAME in sys.modules:
    _legacy = sys.modules[_LEGACY_NAME]
else:
    spec = importlib.util.spec_from_file_location(_LEGACY_NAME, _LEGACY_PATH)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"Cannot load legacy parser from {_LEGACY_PATH}")
    _legacy = importlib.util.module_from_spec(spec)
    sys.modules[_LEGACY_NAME] = _legacy
    spec.loader.exec_module(_legacy)  # type: ignore[call-arg]

parse_source = getattr(_legacy, "parse_source", None)
parse = getattr(_legacy, "parse", None) or parse_source
Parser = getattr(_legacy, "Parser", None)

if parse is None or parse_source is None or Parser is None:  # pragma: no cover - defensive
    raise AttributeError("Legacy parser missing required entrypoints")

__all__ = ["parse", "parse_source", "ParseError", "Parser"]
