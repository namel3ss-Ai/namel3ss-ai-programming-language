"""
Packaging models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class AppBundle:
    app_name: str
    pages: List[str]
    flows: List[str]
    agents: List[str]
    plugins: List[str]
    models: List[str]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BundleManifest:
    app_name: str
    entrypoint: str
    bundle_type: str
    version: str
    created_at: str
    runtime: Dict[str, Any]
    env: Dict[str, str]
    assets: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_bundle(
        cls,
        app_name: str,
        entrypoint: str,
        bundle_type: str,
        env: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        assets: Optional[List[str]] = None,
    ) -> "BundleManifest":
        return cls(
            app_name=app_name,
            entrypoint=entrypoint,
            bundle_type=bundle_type,
            version="1.0",
            created_at=datetime.now(timezone.utc).isoformat(),
            runtime={"python": "3.11"},
            env=env or {},
            assets=assets or [],
            metadata=metadata or {},
        )
