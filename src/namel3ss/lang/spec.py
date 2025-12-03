"""
Formal language contracts for Namel3ss V3-alpha.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Iterable, Set


class BlockKind(str, Enum):
    APP = "app"
    PAGE = "page"
    MODEL = "model"
    AI = "ai"
    AGENT = "agent"
    FLOW = "flow"
    MEMORY = "memory"
    PLUGIN = "plugin"
    DATASET = "dataset"
    INDEX = "index"
    SECTION = "section"
    COMPONENT = "component"


@dataclass(frozen=True)
class BlockContract:
    required_fields: Set[str] = field(default_factory=set)
    optional_fields: Set[str] = field(default_factory=set)
    allowed_children: Set[BlockKind] = field(default_factory=set)
    disallowed_fields: Set[str] = field(default_factory=set)

    def all_fields(self) -> Set[str]:
        return set(self.required_fields) | set(self.optional_fields)


def _fields(iterable: Iterable[str]) -> Set[str]:
    return set(iterable)


LANG_SPEC: Dict[BlockKind, BlockContract] = {
    BlockKind.APP: BlockContract(
        required_fields=_fields(["name", "entry_page"]),
        optional_fields=_fields(["description"]),
        allowed_children=_fields([BlockKind.PAGE]),
    ),
    BlockKind.PAGE: BlockContract(
        required_fields=_fields(["name", "route"]),
        optional_fields=_fields(["title", "description"]),
        allowed_children=_fields([BlockKind.SECTION, BlockKind.COMPONENT]),
    ),
    BlockKind.MODEL: BlockContract(
        required_fields=_fields(["name", "provider"]),
        optional_fields=set(),
    ),
    BlockKind.AI: BlockContract(
        required_fields=_fields(["name", "model_name", "input_source"]),
    ),
    BlockKind.AGENT: BlockContract(
        required_fields=_fields(["name"]),
        optional_fields=_fields(["goal", "personality"]),
    ),
    BlockKind.FLOW: BlockContract(
        required_fields=_fields(["name"]),
        optional_fields=_fields(["description"]),
        allowed_children=_fields([BlockKind.AI, BlockKind.AGENT]),
    ),
    BlockKind.MEMORY: BlockContract(
        required_fields=_fields(["name", "memory_type"]),
    ),
    BlockKind.PLUGIN: BlockContract(
        required_fields=_fields(["name"]),
        optional_fields=_fields(["description"]),
    ),
    BlockKind.DATASET: BlockContract(
        required_fields=_fields(["name"]),
    ),
    BlockKind.INDEX: BlockContract(
        required_fields=_fields(["name"]),
    ),
    BlockKind.SECTION: BlockContract(
        required_fields=_fields(["name"]),
        allowed_children=_fields([BlockKind.COMPONENT]),
    ),
    BlockKind.COMPONENT: BlockContract(
        required_fields=_fields(["type"]),
        optional_fields=_fields(["props"]),
    ),
}
