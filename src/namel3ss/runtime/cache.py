from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Dict, Optional, Protocol


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


class ProviderCacheBackend(Protocol):
    async def get(self, key: str) -> Any | None: ...

    async def set(self, key: str, value: Any, ttl: float | None = None) -> None: ...


@dataclass
class _CacheEntry:
    value: Any
    expires_at: float | None


class InMemoryProviderCache(ProviderCacheBackend):
    """
    Simple in-process cache with TTL support. Not distributed.
    """

    def __init__(self) -> None:
        self._store: Dict[str, _CacheEntry] = {}

    async def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if not entry:
            return None
        if entry.expires_at is not None and entry.expires_at < time.monotonic():
            self._store.pop(key, None)
            return None
        return entry.value

    async def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        expires = time.monotonic() + ttl if ttl else None
        self._store[key] = _CacheEntry(value=value, expires_at=expires)


def get_default_provider_cache() -> ProviderCacheBackend | None:
    if not _env_bool("N3_PROVIDER_CACHE_ENABLED", False):
        return None
    return InMemoryProviderCache()


def get_provider_cache_ttl_seconds() -> float:
    return _env_float("N3_PROVIDER_CACHE_TTL_SECONDS", 300.0)


def _stable_json(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, default=str)
    except Exception:
        return str(value)


def build_provider_cache_key(provider: str, model: str | None, payload: dict) -> str:
    data = {
        "provider": provider or "unknown",
        "model": model or "unknown",
        "payload": payload,
    }
    blob = _stable_json(data)
    return sha256(blob.encode("utf-8")).hexdigest()


def cache_get_sync(cache: ProviderCacheBackend | None, key: str) -> Any | None:
    if cache is None:
        return None
    try:
        return asyncio.run(cache.get(key))
    except RuntimeError:
        # When already in an event loop, create a new task and run with loop
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(cache.get(key))


def cache_set_sync(cache: ProviderCacheBackend | None, key: str, value: Any, ttl: float | None = None) -> None:
    if cache is None:
        return
    try:
        asyncio.run(cache.set(key, value, ttl))
    except RuntimeError:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(cache.set(key, value, ttl))

