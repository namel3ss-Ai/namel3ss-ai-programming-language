"""
Plugin data models.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class PluginInfo:
    name: str
    description: Optional[str] = None
    enabled: bool = True
