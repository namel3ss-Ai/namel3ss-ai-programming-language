from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Set, Tuple


@dataclass(frozen=True)
class FieldSpec:
    name: str
    required: bool
    field_type: str  # "string", "identifier", "int", "bool", "list", "mapping"
    description: str
    allowed_values: Optional[Set[str]] = None


@dataclass(frozen=True)
class BlockContract:
    kind: str
    description: str
    required_fields: Tuple[FieldSpec, ...]
    optional_fields: Tuple[FieldSpec, ...]
    allowed_children: Tuple[str, ...]
    forbidden_children: Tuple[str, ...] = ()
    unique_name_scope: Optional[str] = None

    def all_field_names(self) -> Set[str]:
        return {f.name for f in self.required_fields} | {f.name for f in self.optional_fields}
