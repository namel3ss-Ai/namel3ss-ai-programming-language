"""
Server entrypoint for deployed environments.
"""

from __future__ import annotations

import os
from pathlib import Path

from namel3ss.server import create_app


def _load_source() -> str:
    source_path = Path(os.getenv("N3_SOURCE_PATH", "app.ai"))
    if source_path.exists():
        return source_path.read_text(encoding="utf-8")
    return ""


def build_app():
    # The server factory reads code from incoming requests; we can preload code if desired.
    # For now, keep the default factory behaviour.
    return create_app()


app = build_app()
