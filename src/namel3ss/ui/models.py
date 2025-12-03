"""
Runtime UI models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class UIComponent:
    id: str
    type: str
    props: dict[str, Any] = field(default_factory=dict)


@dataclass
class UISection:
    name: str
    components: List[UIComponent] = field(default_factory=list)


@dataclass
class UIPage:
    name: str
    title: Optional[str]
    route: Optional[str]
    sections: List[UISection] = field(default_factory=list)
