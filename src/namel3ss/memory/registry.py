from __future__ import annotations

import json
from typing import Any, Dict

from ..config import N3Config, load_config
from ..errors import Namel3ssError
from ..secrets.manager import SecretsManager
from .conversation import (
    ConversationMemoryBackend,
    InMemoryConversationMemoryBackend,
    SqliteConversationMemoryBackend,
)


def _load_memory_store_specs(secrets: SecretsManager) -> Dict[str, Dict[str, Any]]:
    raw = secrets.get("N3_MEMORY_STORES_JSON")
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except Exception:
        return {}
    return {}


def _build_backend(name: str, spec: Dict[str, Any] | None) -> ConversationMemoryBackend:
    kind = str((spec or {}).get("kind") or "in_memory").lower()
    if kind == "in_memory":
        return InMemoryConversationMemoryBackend()
    if kind == "sqlite":
        url = (spec or {}).get("url") or (spec or {}).get("path")
        if not url:
            raise Namel3ssError(
                f"N3L-1204: Memory store '{name}' of kind 'sqlite' requires a 'url' value."
            )
        return SqliteConversationMemoryBackend(url=url)
    raise Namel3ssError(
        f"N3L-1204: Memory store '{name}' specifies unsupported kind '{kind}'."
    )


def build_memory_store_registry(secrets: SecretsManager, config: N3Config | None = None) -> Dict[str, ConversationMemoryBackend]:
    cfg = config or load_config()
    specs: Dict[str, Dict[str, Any]] = {}
    specs.update(getattr(cfg, "memory_stores", {}) or {})
    specs.update(_load_memory_store_specs(secrets))
    registry: Dict[str, ConversationMemoryBackend] = {}
    for name, spec in specs.items():
        registry[name] = _build_backend(name, spec)
    if "default_memory" not in registry:
        registry["default_memory"] = InMemoryConversationMemoryBackend()
    return registry
