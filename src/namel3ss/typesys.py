"""
Foundational types for the Namel3ss V3 type system.

This module currently provides minimal scaffolding and will be expanded with
optional typing, inference, and validation in later iterations.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class TypeRef:
    """Reference to a type by name."""

    name: str
    nullable: bool = False
    generic_of: Optional[str] = None
