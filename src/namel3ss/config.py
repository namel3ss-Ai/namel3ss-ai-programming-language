"""
Centralized configuration loader for providers, models, and backends.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class N3Config:
    default_chat_model: Optional[str] = None
    default_embedding_model: Optional[str] = None
    database_url: Optional[str] = None
    providers: Dict[str, Dict[str, str]] = field(default_factory=dict)
    memory_stores: Dict[str, Dict[str, str]] = field(default_factory=dict)


def load_config(env: Optional[dict] = None) -> N3Config:
    environ = env or os.environ
    providers: Dict[str, Dict[str, str]] = {}
    memory_stores: Dict[str, Dict[str, str]] = {}
    # Support a JSON blob of providers if offered (optional).
    raw_providers = environ.get("N3_PROVIDERS_JSON")
    if raw_providers:
        try:
            providers.update(json.loads(raw_providers))
        except Exception:
            providers = {}

    def _provider_entry(name: str, keys: list[str]) -> None:
        data: Dict[str, str] = {}
        for key in keys:
            val = environ.get(key)
            if val:
                data[key] = val
        if data:
            providers[name] = data

    _provider_entry("openai", ["N3_OPENAI_API_KEY", "OPENAI_API_KEY", "N3_OPENAI_BASE_URL"])
    _provider_entry("anthropic", ["N3_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY", "N3_ANTHROPIC_BASE_URL"])
    _provider_entry("gemini", ["N3_GEMINI_API_KEY", "GEMINI_API_KEY", "N3_GEMINI_BASE_URL"])

    raw_stores = environ.get("N3_MEMORY_STORES_JSON")
    if raw_stores:
        try:
            memory_stores.update(json.loads(raw_stores))
        except Exception:
            memory_stores = {}

    return N3Config(
        default_chat_model=environ.get("N3_DEFAULT_CHAT_MODEL") or environ.get("DEFAULT_CHAT_MODEL"),
        default_embedding_model=environ.get("N3_DEFAULT_EMBEDDING_MODEL") or environ.get("DEFAULT_EMBEDDING_MODEL"),
        database_url=environ.get("DATABASE_URL") or environ.get("N3_DATABASE_URL"),
        providers=providers,
        memory_stores=memory_stores,
    )
