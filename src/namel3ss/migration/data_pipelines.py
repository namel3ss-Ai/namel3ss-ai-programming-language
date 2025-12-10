from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass
class DataPipelinesMigrationResult:
    path: Path
    rewrites: int = 0
    warnings: List[str] = field(default_factory=list)
    details: List[str] = field(default_factory=list)
    changed: bool = False


_FROM_WHERE = re.compile(
    r'^(?P<indent>\s*)(?:(?:let)\s+(?P<name>[A-Za-z_][\w]*)\s+be\s+)?all\s+(?P<var>[A-Za-z_][\w]*)(?:\.(?P<field>[A-Za-z_][\w]*))?\s+from\s+(?P<source>.+?)\s+where\s+(?P<predicate>.+)$'
)
_WHERE_ONLY = re.compile(
    r'^(?P<indent>\s*)(?:(?:let)\s+(?P<name>[A-Za-z_][\w]*)\s+be\s+)?all\s+(?P<source>[A-Za-z_][\w]*)\s+where\s+(?P<predicate>.+)$'
)
_SUM_OF_ALL = re.compile(r"\b(sum|mean|minimum|maximum)\s+of\s+all\b", re.IGNORECASE)


def _rewrite_predicate(predicate: str, legacy_var: str) -> str:
    if not legacy_var:
        return predicate
    try:
        return re.sub(rf"\b{re.escape(legacy_var)}\b", "row", predicate)
    except re.error:
        return predicate


def rewrite_source(source: str) -> tuple[str, DataPipelinesMigrationResult]:
    lines = source.splitlines(keepends=True)
    rewritten: list[str] = []
    result = DataPipelinesMigrationResult(path=Path())
    for idx, line in enumerate(lines, start=1):
        m = _FROM_WHERE.match(line.rstrip("\n"))
        if m:
            if m.group("field"):
                result.warnings.append(
                    f"Legacy projection 'all {m.group('var')}.{m.group('field')} from ...' at line {idx} not auto-migrated; convert manually."
                )
                rewritten.append(line)
                continue
            indent = m.group("indent") or ""
            name = m.group("name") or "filtered_rows"
            source_expr = m.group("source").strip()
            predicate = _rewrite_predicate(m.group("predicate").strip(), m.group("var") or "")
            rewritten.append(f"{indent}let {name} be {source_expr}:\n")
            rewritten.append(f"{indent}  keep rows where {predicate}\n")
            result.rewrites += 1
            result.changed = True
            result.details.append(
                f"Rewriting legacy 'all ... from ... where ...' to pipeline at line {idx}"
            )
            continue
        m2 = _WHERE_ONLY.match(line.rstrip("\n"))
        if m2:
            indent = m2.group("indent") or ""
            name = m2.group("name") or "filtered_rows"
            source_expr = m2.group("source").strip()
            predicate = _rewrite_predicate(m2.group("predicate").strip(), "item")
            rewritten.append(f"{indent}let {name} be {source_expr}:\n")
            rewritten.append(f"{indent}  keep rows where {predicate}\n")
            result.rewrites += 1
            result.changed = True
            result.details.append("Rewriting legacy 'all ... where ...' to pipeline")
            continue
        if _SUM_OF_ALL.search(line):
            result.warnings.append(
                f"Legacy aggregate with 'sum of all' found at line {idx}; please convert to pipeline + aggregate manually."
            )
            rewritten.append(line)
            continue
        rewritten.append(line)
    return "".join(rewritten), result


def migrate_file(path: Path, *, write: bool = False, backup: bool = True) -> DataPipelinesMigrationResult:
    original = path.read_text(encoding="utf-8")
    migrated, result = rewrite_source(original)
    result.path = path
    if write and result.changed:
        if backup:
            path.with_suffix(path.suffix + ".bak").write_text(original, encoding="utf-8")
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(migrated, encoding="utf-8")
        tmp_path.replace(path)
    return result


def migrate_path(root: Path, *, write: bool = False, backup: bool = True) -> list[DataPipelinesMigrationResult]:
    results: list[DataPipelinesMigrationResult] = []
    for file in root.rglob("*.ai"):
        results.append(migrate_file(file, write=write, backup=backup))
    return results
