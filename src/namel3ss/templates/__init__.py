from __future__ import annotations

from pathlib import Path
from .manager import get_template_path, list_templates, scaffold_project, TEMPLATES_ROOT


def init_template(name: str, target_dir: Path, force: bool = False) -> Path:
    """Compatibility shim to scaffold a template into target_dir."""
    scaffold_project(name, target_dir, project_name=target_dir.name, force=force)
    return target_dir


__all__ = ["get_template_path", "list_templates", "scaffold_project", "init_template", "TEMPLATES_ROOT"]
