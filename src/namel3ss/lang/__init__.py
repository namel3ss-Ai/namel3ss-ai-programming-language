"""
Language specification utilities (non-parsing).
"""

from .spec import BlockKind, BlockContract, LANG_SPEC
from .validator import validate_module

__all__ = ["BlockKind", "BlockContract", "LANG_SPEC", "validate_module"]
