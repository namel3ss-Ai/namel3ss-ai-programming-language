from __future__ import annotations

from pathlib import Path
from typing import List


def get_examples_root() -> Path:
    """Return the absolute path to the /examples root."""
    return Path(__file__).resolve().parents[3] / "examples"


def list_examples() -> List[str]:
    """Return available example names (folder names)."""
    root = get_examples_root()
    if not root.exists():
        return []
    names = []
    for child in root.iterdir():
        if child.is_dir():
            ai_file = child / f"{child.name}.ai"
            if ai_file.exists():
                names.append(child.name)
    return sorted(names)


def resolve_example_path(name: str) -> Path:
    """Resolve the path to /examples/<name>/<name>.ai."""
    root = get_examples_root()
    path = root / name / f"{name}.ai"
    if not path.exists():
        raise FileNotFoundError(f"Example '{name}' not found at {path}")
    return path
