"""
Plugin manifest parsing utilities.
"""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class PluginManifest:
    id: Optional[str]
    name: str
    version: str
    description: str
    author: Optional[str] = None
    n3_core_version: Optional[str] = None
    entry_point: Optional[str] = None
    entrypoints: Dict[str, str] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    homepage: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True

    @classmethod
    def from_file(cls, path: str | Path) -> "PluginManifest":
        p = Path(path)
        if not p.exists():
            raise ValueError(f"Manifest not found at {p}")

        if p.suffix == ".toml":
            data = tomllib.loads(p.read_text(encoding="utf-8"))
            required = ["id", "name", "version", "description", "entrypoints"]
            missing = [k for k in required if k not in data or not data.get(k)]
            if missing:
                raise ValueError(f"Missing required fields in manifest {p}: {', '.join(missing)}")
            entrypoints = data.get("entrypoints") or {}
            return cls(
                id=data.get("id"),
                name=data["name"],
                version=data["version"],
                description=data["description"],
                author=data.get("author"),
                n3_core_version=data.get("n3_core_version"),
                entrypoints=entrypoints,
                tags=data.get("tags") or [],
                homepage=data.get("homepage"),
                extra=data.get("extra") or {},
            )

        if p.suffix == ".json":
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except Exception as exc:  # pragma: no cover - json error path
                raise ManifestError(f"Invalid manifest JSON at {p}: {exc}") from exc
            required = ["name", "version", "description", "entry_point"]
            missing = [k for k in required if not data.get(k)]
            if missing:
                raise ManifestError(f"Missing required fields in manifest {p}: {', '.join(missing)}")
            entrypoints = data.get("entrypoints") or {}
            entry_point = data.get("entry_point")
            if entry_point and not entrypoints:
                entrypoints = {"main": entry_point}
            return cls(
                id=data.get("id") or data["name"],
                name=data["name"],
                version=data["version"],
                description=data["description"],
                author=data.get("author"),
                n3_core_version=data.get("n3_core_version"),
                entry_point=entry_point,
                entrypoints=entrypoints,
                tags=data.get("tags") or [],
                homepage=data.get("homepage"),
                extra=data.get("extra") or {},
                enabled=data.get("enabled", True),
            )

        raise ManifestError(f"Unsupported manifest type: {p.suffix}")


class ManifestError(ValueError):
    pass


def load_manifest(path: str | Path) -> PluginManifest:
    try:
        return PluginManifest.from_file(path)
    except ManifestError:
        raise
    except Exception as exc:
        raise ManifestError(str(exc)) from exc
