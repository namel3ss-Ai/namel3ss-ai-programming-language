"""
Plugin data models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Dict


@dataclass
class PluginInfo:
    id: str
    name: str
    description: Optional[str] = None
    version: str | None = None
    author: str | None = None
    compatible: bool = True
    enabled: bool = True
    loaded: bool = False
    errors: List[str] = field(default_factory=list)
    path: Optional[str] = None
    entrypoints: Dict[str, str] = field(default_factory=dict)
    contributions: Dict[str, List[str]] = field(default_factory=dict)
