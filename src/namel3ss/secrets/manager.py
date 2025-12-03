"""
Environment-based secrets manager.
"""

from __future__ import annotations

import os
from typing import Mapping, List, Dict

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

    def get_model_config(self, model_name: str) -> Dict[str, str]:
        """
        Read per-model configuration from environment variables:
        N3_MODEL_<NAME>_PROVIDER, _MODEL, _BASE_URL, _RESPONSE_PATH, plus any extra options.
        """
        prefix = f"N3_MODEL_{model_name.upper()}_"
        cfg: Dict[str, str] = {}
        for key, value in self._env.items():
            if key.startswith(prefix):
                suffix = key.removeprefix(prefix)
                if suffix == "PROVIDER":
                    cfg["provider"] = value
                elif suffix == "MODEL":
                    cfg["model"] = value
                elif suffix == "BASE_URL":
                    cfg["base_url"] = value
                elif suffix == "RESPONSE_PATH":
                    cfg["response_path"] = value
                else:
                    cfg.setdefault("options", {})[suffix.lower()] = value
        return cfg

    def get_provider_config(self, provider_name: str) -> Dict[str, str]:
        """Placeholder for future provider-wide config; currently returns env values matching provider name."""
        prefix = f"N3_PROVIDER_{provider_name.upper()}_"
        cfg: Dict[str, str] = {}
        for key, value in self._env.items():
            if key.startswith(prefix):
                suffix = key.removeprefix(prefix).lower()
                cfg[suffix] = value
        return cfg

    def get_embedding_provider_name(self) -> str | None:
        return self.get("N3_EMBEDDINGS_PROVIDER")

    def get_embedding_model(self) -> str | None:
        return self.get("N3_EMBEDDINGS_MODEL")

    def get_embedding_base_url(self) -> str | None:
        return self.get("N3_EMBEDDINGS_BASE_URL")

    def get_embedding_response_path(self) -> str | None:
        return self.get("N3_EMBEDDINGS_RESPONSE_PATH")

    def get_rag_index_backend(self, index_name: str) -> str | None:
        return self.get(f"N3_RAG_INDEX_{index_name.upper()}_BACKEND")

    def get_pgvector_dsn(self) -> str | None:
        return self.get("N3_RAG_PGVECTOR_DSN") or self.get("N3_PGVECTOR_DSN")

    def get_pgvector_table(self, index_name: str) -> str | None:
        return self.get(f"N3_RAG_INDEX_{index_name.upper()}_PG_TABLE")

    def get_faiss_index_path(self, index_name: str) -> str | None:
        return self.get(f"N3_RAG_INDEX_{index_name.upper()}_FAISS_INDEX_PATH")
