"""
Overlay storage for runtime configuration adjustments.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict


@dataclass
class RuntimeOverlay:
    models: Dict[str, Dict] = field(default_factory=dict)
    flows: Dict[str, Dict] = field(default_factory=dict)
    prompts: Dict[str, str] = field(default_factory=dict)
    tools: Dict[str, Dict] = field(default_factory=dict)
    memory_policies: Dict[str, Dict] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "models": self.models,
            "flows": self.flows,
            "prompts": self.prompts,
            "tools": self.tools,
            "memory_policies": self.memory_policies,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RuntimeOverlay":
        return cls(
            models=data.get("models", {}),
            flows=data.get("flows", {}),
            prompts=data.get("prompts", {}),
            tools=data.get("tools", {}),
            memory_policies=data.get("memory_policies", {}),
        )


class OverlayStore:
    def __init__(self, path: Path):
        self.path = path
        if not self.path.exists():
            self.save(RuntimeOverlay())

    def load(self) -> RuntimeOverlay:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return RuntimeOverlay.from_dict(data)

    def save(self, overlay: RuntimeOverlay) -> None:
        self.path.write_text(json.dumps(overlay.to_dict(), indent=2), encoding="utf-8")

    def update(self, overlay: RuntimeOverlay) -> None:
        self.save(overlay)
