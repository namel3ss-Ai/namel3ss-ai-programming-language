"""
Hatch build hook to bundle the prebuilt Studio frontend into the Python wheel.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    """
    Copies ./studio/dist (or a fallback) into src/namel3ss/studio_static so the
    wheel always contains frontend assets without requiring Node at install time.
    """

    PLUGIN_NAME = "custom"

    def initialize(self, version: str, build_data: dict) -> None:  # type: ignore[override]
        project_root = Path(self.root)
        studio_dir = project_root / "studio"
        dist_dir = studio_dir / "dist"
        fallback_dir = studio_dir / "static"
        target_dir = project_root / "src" / "namel3ss" / "studio_static"

        target_dir.mkdir(parents=True, exist_ok=True)
        self._clean_target(target_dir)

        source_dir = self._select_source(studio_dir, dist_dir, fallback_dir)
        if source_dir is None:
            raise FileNotFoundError(
                "Studio build artifacts missing. Run `npm install && npm run build` in ./studio "
                "or provide prebuilt assets in studio/static."
            )

        shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)
        init_file = target_dir / "__init__.py"
        if not init_file.exists():
            init_file.write_text('"""Bundled Studio frontend assets."""\n', encoding="utf-8")

    def _select_source(self, studio_dir: Path, dist_dir: Path, fallback_dir: Path) -> Path | None:
        if dist_dir.exists() and any(dist_dir.iterdir()):
            return dist_dir

        if self._build_frontend(studio_dir, dist_dir):
            if dist_dir.exists() and any(dist_dir.iterdir()):
                return dist_dir

        if fallback_dir.exists() and any(fallback_dir.iterdir()):
            return fallback_dir
        return None

    def _build_frontend(self, studio_dir: Path, dist_dir: Path) -> bool:
        npm = shutil.which("npm") or shutil.which("pnpm")
        if not npm:
            self.app.display_warning("npm/pnpm not available, skipping Studio frontend build.")
            return False
        package_json = studio_dir / "package.json"
        if not package_json.exists():
            self.app.display_warning("Studio package.json not found; skipping frontend build.")
            return False

        commands = []
        if not (studio_dir / "node_modules").exists():
            commands.append([npm, "install"])
        commands.append([npm, "run", "build"])

        for cmd in commands:
            try:
                subprocess.run(cmd, cwd=studio_dir, check=True)
            except Exception as exc:  # pragma: no cover - build-time surface
                self.app.display_warning(f"Studio build command failed: {' '.join(cmd)} ({exc})")
                return False

        return dist_dir.exists() and any(dist_dir.iterdir())

    def _clean_target(self, target_dir: Path) -> None:
        for child in target_dir.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
