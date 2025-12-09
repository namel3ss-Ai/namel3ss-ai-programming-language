from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from ..observability.metrics import default_metrics
from ..runtime.vectorstores import VectorStoreRegistry


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def get_vector_memory_settings() -> tuple[bool, str, int]:
    """
    Resolve vector memory env configuration.
    """

    enabled = _env_bool("N3_VECTOR_MEMORY_ENABLED", False)
    store_name = os.getenv("N3_VECTOR_MEMORY_STORE_NAME", "default_vector")
    top_k = _env_int("N3_VECTOR_MEMORY_TOP_K", 5)
    return enabled, store_name, top_k


def upsert_conversation_chunks(
    vector_registry: VectorStoreRegistry,
    store_name: str,
    messages: list[dict[str, Any]],
    metadata: dict[str, Any] | None = None,
) -> None:
    """
    Upsert conversation turns as vector chunks for long-term recall.
    """

    if not messages:
        return
    texts: List[str] = []
    ids: List[str] = []
    meta_list: List[dict[str, Any]] = []
    for idx, msg in enumerate(messages):
        role = msg.get("role", "user")
        content = str(msg.get("content", "")).strip()
        if not content:
            continue
        texts.append(f"{role}: {content}")
        ids.append(f"msg-{idx}")
        meta_list.append(metadata or {})
    vector_registry.index_texts(store_name, ids, texts, metadata=meta_list)
    try:
        default_metrics.record_vector_upsert()
    except Exception:
        pass


def retrieve_relevant_chunks(
    vector_registry: VectorStoreRegistry,
    store_name: str,
    query: str,
    top_k: int = 5,
    metadata_filter: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Retrieve top-K chunks relevant to a query.
    """

    results = vector_registry.query(store_name, query, top_k=top_k)
    if metadata_filter:
        filtered: list[dict[str, Any]] = []
        for res in results:
            meta = res.get("metadata") or {}
            if all(meta.get(k) == v for k, v in metadata_filter.items()):
                filtered.append(res)
        results = filtered
    try:
        default_metrics.record_vector_query()
    except Exception:
        pass
    return results
