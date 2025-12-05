"""
Language specification utilities (non-parsing).
"""

from .spec import (
    LANG_SPEC,
    BlockContract,
    BlockKind,
    FieldSpec,
    all_contracts,
    get_contract,
    validate_ir,
    validate_ir_module,
)
from .validator import validate_module

__all__ = [
    "FieldSpec",
    "BlockContract",
    "BlockKind",
    "LANG_SPEC",
    "get_contract",
    "all_contracts",
    "validate_ir",
    "validate_ir_module",
    "validate_module",
]
