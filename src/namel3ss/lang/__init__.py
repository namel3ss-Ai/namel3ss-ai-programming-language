"""
Language specification utilities (non-parsing).
"""

from .spec import (
    FieldSpec,
    BlockContract,
    BlockKind,
    LANG_SPEC,
    get_contract,
    all_contracts,
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
