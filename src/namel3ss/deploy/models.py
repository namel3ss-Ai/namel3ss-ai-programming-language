"""
Deployment target and artifact models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict


class DeployTargetKind(str, Enum):
    SERVER = "server"
    WORKER = "worker"
    DOCKER = "docker"
    SERVERLESS_AWS = "serverless-aws"
    SERVERLESS_CLOUDFLARE = "serverless-cloudflare"
    DESKTOP = "desktop"
    MOBILE = "mobile"


@dataclass
class DeployTargetConfig:
    kind: DeployTargetKind
    name: str
    output_dir: Path
    env: Dict[str, str] | None = None
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BuildArtifact:
    kind: DeployTargetKind
    path: Path
    metadata: Dict[str, Any] = field(default_factory=dict)
