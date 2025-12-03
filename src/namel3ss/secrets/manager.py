"""
Environment-based secrets manager.
"""

from __future__ import annotations

import os
from typing import Mapping, List

from .models import Secret


class SecretsManager:
    def __init__(self, env: Mapping[str, str] | None = None) -> None:
        self._env = dict(env) if env is not None else dict(os.environ)

    def get(self, name: str) -> str | None:
        return self._env.get(name)

    def list(self) -> List[Secret]:
        return [Secret(name=k, value=v) for k, v in self._env.items()]

    def is_enabled(self, name: str) -> bool:
        value = self.get(name)
        if value is None:
            return False
        return value.lower() in {"1", "true", "yes", "on"}
