"""
Plugin manifest parsing and validation.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

from .versioning import is_compatible, parse_version


@dataclass
class PluginManifest:
    id: str
    name: str
    version: str
    description: str
    author: str
    n3_core_version: str
    entrypoints: Dict[str, str]

    @classmethod
    def from_file(cls, path: Path) -> "PluginManifest":
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict) -> "PluginManifest":
        required = ["id", "name", "version", "description", "author", "n3_core_version"]
        missing = [k for k in required if k not in data]
        if missing:
            raise ValueError(f"Missing manifest fields: {', '.join(missing)}")
        # validate version syntax
        parse_version(str(data["version"]))
        entrypoints = data.get("entrypoints") or {}
        if not isinstance(entrypoints, dict):
            raise ValueError("entrypoints must be a table/dict")
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            version=str(data["version"]),
            description=str(data["description"]),
            author=str(data["author"]),
            n3_core_version=str(data["n3_core_version"]),
            entrypoints={str(k): str(v) for k, v in entrypoints.items()},
        )

    def is_compatible_with(self, core_version: str) -> bool:
        return is_compatible(core_version, self.n3_core_version)
