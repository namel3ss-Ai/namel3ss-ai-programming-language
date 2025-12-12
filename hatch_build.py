"""
Hatch build hook to bundle the prebuilt Studio frontend into the Python wheel.
"""

from __future__ import annotations

from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    """
    Ensures packaged Studio assets (src/namel3ss/studio_static) ship with the wheel.
    """

    PLUGIN_NAME = "custom"

    def initialize(self, version: str, build_data: dict) -> None:  # type: ignore[override]
        project_root = Path(self.root)
        target_dir = project_root / "src" / "namel3ss" / "studio_static"
        if not target_dir.exists():
            raise FileNotFoundError("Studio static assets missing at src/namel3ss/studio_static.")
        index_path = target_dir / "index.html"
        if not index_path.exists():
            raise FileNotFoundError("Studio static assets incomplete (index.html missing).")
        init_file = target_dir / "__init__.py"
        if not init_file.exists():
            init_file.write_text('"""Bundled Studio frontend assets."""\n', encoding="utf-8")
