from __future__ import annotations

import shutil
from pathlib import Path
from typing import List


TEMPLATES_DIR = Path(__file__).resolve().parents[3] / "templates"


def list_templates() -> List[str]:
    if not TEMPLATES_DIR.exists():
        return []
    return sorted([p.name for p in TEMPLATES_DIR.iterdir() if p.is_dir()])


def init_template(name: str, target_dir: Path, force: bool = False) -> Path:
    source = TEMPLATES_DIR / name
    if not source.exists():
        raise ValueError(f"Template '{name}' not found")
    target_dir = target_dir.resolve()
    if target_dir.exists() and any(target_dir.iterdir()) and not force:
        raise FileExistsError(f"Target directory '{target_dir}' is not empty. Use --force to overwrite.")
    if not target_dir.exists():
        target_dir.mkdir(parents=True, exist_ok=True)
    else:
        if force:
            shutil.rmtree(target_dir)
            target_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target_dir, dirs_exist_ok=True)
    return target_dir
