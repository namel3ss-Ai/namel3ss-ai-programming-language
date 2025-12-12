#!/usr/bin/env python3
"""
Rewrite legacy declaration headers to the `is` form.

Rules:
- Targets keywords: app, page, flow, agent, tool, record, model, macro
- Rewrites only when the keyword starts the line (allowing leading whitespace)
- Skips lines already using `is`
- Processes extensions: .py .ai .n3 .md .txt .yaml .yml .toml .json
- Skips common build/venv/cache directories.
"""

from __future__ import annotations

import pathlib
import re
import sys
from typing import Iterable

ROOT = pathlib.Path(__file__).resolve().parents[1]
TARGET_EXTS = {".py", ".ai", ".n3", ".md", ".txt", ".yaml", ".yml", ".toml", ".json"}
SKIP_DIRS = {".git", "node_modules", "dist", "build", "__pycache__", ".venv", "venv"}
KEYWORDS = {"app", "page", "flow", "agent", "tool", "record", "model", "macro"}

pattern = re.compile(
    r'^(\s*)(%s)\s+"(?=[^"])' % "|".join(KEYWORDS),
    re.MULTILINE,
)


def should_skip(path: pathlib.Path) -> bool:
    return any(part in SKIP_DIRS for part in path.parts)


def iter_files(paths: Iterable[pathlib.Path]) -> Iterable[pathlib.Path]:
    for path in paths:
        if path.is_dir():
            if should_skip(path):
                continue
            yield from iter_files(path.iterdir())
        elif path.suffix in TARGET_EXTS and not should_skip(path):
            yield path


def rewrite_text(text: str) -> tuple[str, int]:
    count = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal count
        leading, keyword = match.groups()
        line_rest = text[match.end() : text.find("\n", match.start())]
        if f"{keyword} is " in line_rest:
            return match.group(0)
        count += 1
        return f'{leading}{keyword} is "'

    new_text = pattern.sub(repl, text)
    return new_text, count


def main(argv: list[str]) -> int:
    paths = [ROOT / "tests", ROOT / "examples", ROOT / "src", ROOT / "docs"]
    total_replacements = 0
    changed_files: list[pathlib.Path] = []

    for file_path in iter_files(paths):
        original = file_path.read_text(encoding="utf-8")
        rewritten, count = rewrite_text(original)
        if count:
            file_path.write_text(rewritten, encoding="utf-8")
            total_replacements += count
            changed_files.append(file_path)

    print(f"Replacements: {total_replacements}")
    if changed_files:
        print("Changed files:")
        for path in changed_files:
            print(f" - {path.relative_to(ROOT)}")
    else:
        print("No changes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
