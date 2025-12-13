#!/usr/bin/env python3
"""
Rewrite field headers to use `is` in DSL fixtures/templates/examples.

Transforms lines like:
    query:
into:
    query is:

Special handling:
- Bare `source:` block headers are flagged (not rewritten) because nested source
  blocks are invalid; offenders are reported.
- Inline `source: <value>` is rewritten to `source is <value>`.

Idempotent: running multiple times should produce zero further changes.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable


FIELD_HEADERS = {
    "query",
    "model",
    "pipeline",
    "backend",
    "table",
    "frame",
    "record",
    "tool",
    "vector_store",
    "url",
    "file",
}

INLINE_SOURCE_PATTERN = re.compile(r"^(\s*)source\s*:\s+(.+)$")
BARE_SOURCE_PATTERN = re.compile(r"^(\s*)source\s*:\s*$")
FIELD_HEADER_PATTERN = re.compile(
    rf"^(\s*)({'|'.join(sorted(FIELD_HEADERS))})\s*:\s*$"
)

TEXT_EXTS = {".py", ".ai", ".n3", ".md", ".txt", ".yaml", ".yml", ".toml", ".json"}
SKIP_DIRS = {".git", "node_modules", "dist", "build", "__pycache__", ".venv", "venv"}


def iter_targets(base: Path) -> Iterable[Path]:
    if base.is_file():
        if base.suffix in TEXT_EXTS:
            yield base
        return
    for path in base.rglob("*"):
        if path.is_dir():
            if path.name in SKIP_DIRS:
                # Skip walking into skipped dirs
                path.rglob  # no-op to satisfy type checkers
            continue
        if path.suffix in TEXT_EXTS and not any(part in SKIP_DIRS for part in path.parts):
            yield path


def process_file(path: Path) -> tuple[bool, list[str]]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    changed = False
    offenders: list[str] = []
    new_lines: list[str] = []
    for idx, line in enumerate(lines, start=1):
        if BARE_SOURCE_PATTERN.match(line):
            offenders.append(f"{path}:{idx}: bare source block header")
            new_lines.append(line)
            continue
        inline_source = INLINE_SOURCE_PATTERN.match(line)
        if inline_source:
            indent, rest = inline_source.groups()
            new_lines.append(f"{indent}source is {rest}")
            changed = True
            continue
        if FIELD_HEADER_PATTERN.match(line):
            # Avoid touching lines that already contain " is:"
            if " is:" in line:
                new_lines.append(line)
                continue
            indent, field = FIELD_HEADER_PATTERN.match(line).groups()  # type: ignore
            new_lines.append(f"{indent}{field} is:")
            changed = True
            continue
        new_lines.append(line)
    if changed:
        path.write_text("\n".join(new_lines) + ("\n" if text.endswith("\n") else ""), encoding="utf-8")
    return changed, offenders


def main() -> int:
    roots = [Path("tests"), Path("examples"), Path("templates"), Path("docs"), Path("src")]
    total_changed = 0
    offenders: list[str] = []
    for root in roots:
        if not root.exists():
            continue
        for path in iter_targets(root):
            file_changed, file_offenders = process_file(path)
            if file_changed:
                total_changed += 1
            offenders.extend(file_offenders)
    print(f"migrate_is_fields: files changed={total_changed}")
    if offenders:
        print("Nested source block headers found (not rewritten):")
        for line in offenders:
            print(f"  {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
