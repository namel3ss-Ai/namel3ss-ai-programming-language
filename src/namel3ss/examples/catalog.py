"""
Examples catalog for curated demos.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass
class ExampleApp:
    id: str
    name: str
    path: str
    category: str
    description: str
    tags: List[str] = field(default_factory=list)


class ExamplesCatalog:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path("examples")

    def _load_meta(self, meta_path: Path, example_id: str) -> ExampleApp:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        return ExampleApp(
            id=example_id,
            name=data.get("name") or example_id,
            path=str(meta_path.parent),
            category=data.get("category") or "general",
            description=data.get("description") or "",
            tags=data.get("tags") or [],
        )

    def list_examples(self) -> List[ExampleApp]:
        examples: List[ExampleApp] = []
        if not self.root.exists():
            return examples
        for meta in self.root.glob("**/meta.json"):
            example_id = meta.parent.name
            examples.append(self._load_meta(meta, example_id))
        return examples

    def get_example(self, example_id: str) -> ExampleApp | None:
        meta = next((m for m in self.root.glob("**/meta.json") if m.parent.name == example_id), None)
        if not meta:
            return None
        return self._load_meta(meta, example_id)
