from __future__ import annotations

from namel3ss.plugins.sdk import PluginSDK


def register_rag(sdk: PluginSDK) -> None:
    # Register a default in-memory index named "default-rag"
    sdk.rag.register_index("default-rag")
