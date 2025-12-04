"""Template management helpers for project scaffolding."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import List, Optional

# __file__ -> src/namel3ss/templates/manager.py
# parents: [manager.py, templates, namel3ss, src, repo_root]
TEMPLATES_ROOT = Path(__file__).resolve().parents[3] / "templates"


def list_templates() -> List[str]:
    if not TEMPLATES_ROOT.exists():
        return []
    return sorted([p.name for p in TEMPLATES_ROOT.iterdir() if p.is_dir()])


def get_template_path(name: str) -> Path:
    path = TEMPLATES_ROOT / name
    if not path.exists() or not path.is_dir():
        raise FileNotFoundError(f"Template '{name}' not found in {TEMPLATES_ROOT}")
    return path


def _rewrite_app_name(ai_path: Path, project_name: str) -> None:
    text = ai_path.read_text(encoding="utf-8")
    pattern = re.compile(r'^(app\s+")([^"]+)(")', flags=re.MULTILINE)
    new_text, count = pattern.subn(rf'\1{project_name}\3', text, count=1)
    if count > 0:
        ai_path.write_text(new_text, encoding="utf-8")


def scaffold_project(template_name: str, target_dir: Path, project_name: Optional[str] = None, force: bool = False) -> None:
    template_path = get_template_path(template_name)
    if target_dir.exists() and any(target_dir.iterdir()) and not force:
        raise FileExistsError(f"Target directory '{target_dir}' is not empty. Use --force to overwrite.")
    target_dir.mkdir(parents=True, exist_ok=True)
    for item in template_path.rglob("*"):
        rel = item.relative_to(template_path)
        dest = target_dir / rel
        if item.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, dest)
    if project_name:
        for ai_file in target_dir.rglob("*.ai"):
            _rewrite_app_name(ai_file, project_name)
