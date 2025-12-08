"""
Centralized configuration loader for providers, models, and backends.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class ProviderConfig:
    type: str
    api_key: Optional[str] = None
    api_key_env: Optional[str] = None
    base_url: Optional[str] = None
    model_default: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProvidersConfig:
    default: Optional[str] = None
    providers: Dict[str, ProviderConfig] = field(default_factory=dict)


@dataclass
class N3Config:
    default_chat_model: Optional[str] = None
    default_embedding_model: Optional[str] = None
    database_url: Optional[str] = None
    providers: Dict[str, Dict[str, str]] = field(default_factory=dict)
    memory_stores: Dict[str, Dict[str, str]] = field(default_factory=dict)
    providers_config: ProvidersConfig = field(default_factory=ProvidersConfig)


def _build_provider(name: str, raw: Dict[str, Any]) -> ProviderConfig:
    extra = {k: v for k, v in raw.items() if k not in {"type", "api_key", "api_key_env", "base_url", "model_default"}}
    return ProviderConfig(
        type=(raw.get("type") or name).lower(),
        api_key=raw.get("api_key"),
        api_key_env=raw.get("api_key_env"),
        base_url=raw.get("base_url"),
        model_default=raw.get("model_default"),
        extra=extra,
    )


def _load_file_config() -> dict[str, Any]:
    for filename in ("namel3ss.config.json", "namel3ss.toml", "namel3ss.config.toml"):
        path = Path(filename)
        if path.exists():
            try:
                if path.suffix.lower() == ".json":
                    return json.loads(path.read_text(encoding="utf-8"))
                import tomllib  # py3.11+

                return tomllib.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return {}
    return {}


def load_config(env: Optional[dict] = None) -> N3Config:
    environ = env or os.environ
    providers: Dict[str, Dict[str, str]] = {}
    memory_stores: Dict[str, Dict[str, str]] = {}
    providers_config = ProvidersConfig()

    file_config = _load_file_config()
    if isinstance(file_config, dict):
        raw_providers = file_config.get("providers") or {}
        if isinstance(raw_providers, dict):
            for name, raw in raw_providers.items():
                if isinstance(raw, dict):
                    providers_config.providers[name] = _build_provider(name, raw)
        if isinstance(file_config.get("default"), str):
            providers_config.default = file_config.get("default")

    # Support a JSON blob of providers if offered (optional).
    raw_providers = environ.get("N3_PROVIDERS_JSON")
    if raw_providers:
        try:
            providers.update(json.loads(raw_providers))
        except Exception:
            providers = {}
        if not providers_config.providers:
            try:
                parsed = json.loads(raw_providers)
                if isinstance(parsed, dict):
                    for name, raw in parsed.items():
                        if isinstance(raw, dict):
                            providers_config.providers[name] = _build_provider(name, raw)
            except Exception:
                pass

    def _provider_entry(name: str, keys: list[str]) -> None:
        data: Dict[str, str] = {}
        for key in keys:
            val = environ.get(key)
            if val:
                data[key] = val
        if data:
            providers[name] = data

    def _ensure_default_provider(name: str, type_: str, env_keys: list[str]) -> None:
        if name in providers_config.providers:
            return
        selected_env = None
        for key in env_keys:
            if environ.get(key):
                selected_env = key
                break
        if selected_env:
            providers_config.providers[name] = ProviderConfig(
                type=type_,
                api_key_env=selected_env,
            )

    _provider_entry("openai", ["N3_OPENAI_API_KEY", "OPENAI_API_KEY", "N3_OPENAI_BASE_URL"])
    _provider_entry("anthropic", ["N3_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY", "N3_ANTHROPIC_BASE_URL"])
    _provider_entry("gemini", ["N3_GEMINI_API_KEY", "GEMINI_API_KEY", "N3_GEMINI_BASE_URL"])
    _ensure_default_provider("openai_default", "openai", ["N3_OPENAI_API_KEY", "OPENAI_API_KEY"])
    _ensure_default_provider("gemini_default", "gemini", ["N3_GEMINI_API_KEY", "GEMINI_API_KEY"])

    if not providers_config.default:
        if "openai_default" in providers_config.providers:
            providers_config.default = "openai_default"
        elif providers_config.providers:
            providers_config.default = sorted(providers_config.providers.keys())[0]

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
        providers_config=providers_config,
    )
