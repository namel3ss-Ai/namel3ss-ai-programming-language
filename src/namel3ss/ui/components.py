"""
Runtime UI component models for Namel3ss UI Components V3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class UIEventHandler:
    event: str  # "click" | "submit" | "load" | ...
    handler_kind: str  # "flow" | "agent" | "tool"
    target: str
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UIComponentInstance:
    id: str
    kind: str  # "form" | "table" | "chart" | "realtime" | ...
    props: Dict[str, Any] = field(default_factory=dict)
    bindings: Dict[str, Any] = field(default_factory=dict)
    events: List[UIEventHandler] = field(default_factory=list)


@dataclass
class UIEvent:
    component_id: str
    event: str
    payload: Dict[str, Any] = field(default_factory=dict)
    page: Optional[str] = None
    section: Optional[str] = None


@dataclass
class UIEventResult:
    success: bool
    messages: List[str] = field(default_factory=list)
    validation_errors: Dict[str, str] = field(default_factory=dict)
    updated_state: Dict[str, Any] = field(default_factory=dict)
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UIContext:
    app_name: str
    page_name: Optional[str]
    user: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
