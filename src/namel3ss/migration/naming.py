from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple


HEADER_KEYWORDS = [
    "flow",
    "step",
    "page",
    "app",
    "frame",
    "vector_store",
    "ai",
    "agent",
    "tool",
]


@dataclass
class MigrationResult:
    path: Path
    header_rewrites: int = 0
    let_rewrites: int = 0
    set_rewrites: int = 0
    renames: Dict[str, str] | None = None
    changed: bool = False
    suggested_names: List[Tuple[str, str]] = None


def _to_snake(name: str) -> str:
    # Simple camelCase -> snake_case
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()
    return snake


def rewrite_legacy_headers(lines: List[str]) -> Tuple[List[str], int]:
    rewritten = []
    count = 0
    header_pattern = re.compile(
        r'^(\s*)(%s)\s+"([^"]+)"\s*:\s*$' % "|".join(HEADER_KEYWORDS)
    )
    for line in lines:
        m = header_pattern.match(line)
        if m:
            indent, kw, name = m.groups()
            rewritten.append(f'{indent}{kw} is "{name}":\n')
            count += 1
        else:
            rewritten.append(line)
    return rewritten, count


def _rewrite_assignments(lines: List[str]) -> Tuple[List[str], int, int]:
    let_count = 0
    set_count = 0
    rewritten: list[str] = []
    let_pattern = re.compile(r'^(\s*let\s+(constant\s+)?)([A-Za-z_][\w]*)\s*=\s*(.+)$')
    set_pattern = re.compile(r'^(\s*set\s+state\.[A-Za-z_][\w]*)\s*=\s*(.+)$')
    for line in lines:
        let_match = let_pattern.match(line)
        if let_match:
            prefix, const_kw, name, expr = let_match.groups()
            rewritten.append(f"{prefix}{name} be {expr}\n")
            let_count += 1
            continue
        set_match = set_pattern.match(line)
        if set_match:
            target, expr = set_match.groups()
            rewritten.append(f"{target} be {expr}\n")
            set_count += 1
            continue
        rewritten.append(line)
    return rewritten, let_count, set_count


def _suggest_or_apply_names(lines: List[str], apply: bool) -> Tuple[List[str], Dict[str, str], List[Tuple[str, str]]]:
    declared: Dict[str, str] = {}
    suggestions: List[Tuple[str, str]] = []
    let_decl = re.compile(r'^\s*let\s+(constant\s+)?([A-Za-z_][\w]*)\s+')
    content = "".join(lines)
    for line in lines:
        m = let_decl.match(line)
        if not m:
            continue
        name = m.group(2)
        if re.match(r"^[a-z_][a-z0-9_]*$", name):
            continue
        snake = _to_snake(name)
        declared[name] = snake
        suggestions.append((name, snake))
    if not apply or not declared:
        return lines, {}, suggestions

    updated = content
    for old, new in declared.items():
        updated = re.sub(rf"\b{re.escape(old)}\b", new, updated)
    return updated.splitlines(keepends=True), declared, suggestions


def rewrite_source(source: str, *, apply_name_fixes: bool = False) -> MigrationResult:
    lines = source.splitlines(keepends=True)
    result = MigrationResult(path=Path())
    lines, header_ct = rewrite_legacy_headers(lines)
    lines, let_ct, set_ct = _rewrite_assignments(lines)
    lines, renames, suggestions = _suggest_or_apply_names(lines, apply_name_fixes)
    result.header_rewrites = header_ct
    result.let_rewrites = let_ct
    result.set_rewrites = set_ct
    result.renames = renames or None
    result.suggested_names = suggestions or []
    result.changed = header_ct > 0 or let_ct > 0 or set_ct > 0 or bool(renames)
    return result, "".join(lines)


def migrate_source_to_naming_standard(source: str, *, apply_name_fixes: bool = False) -> tuple[str, MigrationResult, dict[str, Any]]:
    """
    Rewrite a single source string to the English naming standard.

    Returns the migrated source, the raw MigrationResult, and a summary dict for API responses.
    """
    result, migrated = rewrite_source(source, apply_name_fixes=apply_name_fixes)
    summary = {
        "headers_rewritten": result.header_rewrites,
        "let_rewritten": result.let_rewrites,
        "set_rewritten": result.set_rewrites,
        "names_renamed": [{"from": old, "to": new} for old, new in (result.renames or {}).items()],
        "suggested_names": [{"from": old, "to": new} for old, new in (result.suggested_names or [])],
        "changed": result.changed,
    }
    return migrated, result, summary


def migrate_file(path: Path, *, write: bool = False, backup: bool = True, apply_name_fixes: bool = False) -> MigrationResult:
    original = path.read_text(encoding="utf-8")
    result, new_content = rewrite_source(original, apply_name_fixes=apply_name_fixes)
    result.path = path
    if write and result.changed:
        if backup:
            backup_path = path.with_suffix(path.suffix + ".bak")
            backup_path.write_text(original, encoding="utf-8")
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(new_content, encoding="utf-8")
        tmp_path.replace(path)
    return result


def migrate_path(
    root: Path,
    *,
    write: bool = False,
    backup: bool = True,
    apply_name_fixes: bool = False,
) -> List[MigrationResult]:
    results: List[MigrationResult] = []
    for file in root.rglob("*.ai"):
        result = migrate_file(file, write=write, backup=backup, apply_name_fixes=apply_name_fixes)
        results.append(result)
    return results
