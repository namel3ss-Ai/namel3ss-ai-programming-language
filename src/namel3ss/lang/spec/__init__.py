"""
Language specification contracts and validator (V3).

This package also preserves backwards-compatible exports for the legacy
`BlockKind` enum and `LANG_SPEC` mapping defined in ``namel3ss.lang.spec`` (the
original module prior to introducing the contract registry). External code that
still imports these names can continue to do so.
"""

from .contracts import BlockContract, FieldSpec
from .registry import all_contracts, get_contract
from .validator import validate_ir

# Backwards-compatible aliases used by older code paths.
validate_ir_module = validate_ir

try:  # Backwards compatibility: expose legacy BlockKind/LANG_SPEC if present.
    from .. import spec as legacy_spec

    BlockKind = getattr(legacy_spec, "BlockKind", None)
    LANG_SPEC = getattr(legacy_spec, "LANG_SPEC", None)
except Exception:  # pragma: no cover - defensive import guard
    BlockKind = None
    LANG_SPEC = None

__all__ = [
    "FieldSpec",
    "BlockContract",
    "get_contract",
    "all_contracts",
    "validate_ir",
    "BlockKind",
    "LANG_SPEC",
]
