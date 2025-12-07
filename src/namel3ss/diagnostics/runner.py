from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Iterable, List, Tuple

from .. import ir, lexer, parser, linting
from ..errors import Namel3ssError
from . import Diagnostic, create_diagnostic, legacy_to_structured
from .pipeline import run_diagnostics


def iter_ai_files(paths: Iterable[Path]) -> List[Path]:
    files: list[Path] = []
    for p in paths:
        if p.is_file() and p.suffix == ".ai":
            files.append(p)
        elif p.is_dir():
            files.extend(child for child in p.rglob("*.ai") if child.is_file())
    return files


def apply_strict_mode(diagnostics: Iterable[Diagnostic], strict: bool) -> Tuple[List[Diagnostic], dict]:
    if not strict:
        diags = list(diagnostics)
        return diags, summary_counts(diags)
    upgraded: list[Diagnostic] = []
    for diag in diagnostics:
        if diag.severity == "warning" and diag.category in {"lang-spec", "semantic"}:
            upgraded.append(replace(diag, severity="error"))
        else:
            upgraded.append(diag)
    return upgraded, summary_counts(upgraded)


def summary_counts(diags: Iterable[Diagnostic]) -> dict[str, int]:
    diags_list = list(diags)
    return {
        "errors": sum(1 for d in diags_list if d.severity == "error"),
        "warnings": sum(1 for d in diags_list if d.severity == "warning"),
        "infos": sum(1 for d in diags_list if d.severity == "info"),
    }


def _parse_file(path: Path) -> tuple[list[Diagnostic], object | None]:
    try:
        source = path.read_text(encoding="utf-8")
        tokens = lexer.Lexer(source, filename=str(path)).tokenize()
        module = parser.Parser(tokens).parse_module()
        if not getattr(module, "declarations", []):
            diag = create_diagnostic(
                "N3-1010",
                file=str(path),
                line=1,
                column=1,
            )
            return [diag], None
        return [], module
    except Namel3ssError as err:
        diag = create_diagnostic(
            "N3-0001",
            message_kwargs={"detail": err.message},
            file=str(path),
            line=err.line,
            column=err.column,
        )
        return [diag], None


def _compile_to_ir(path: Path, module) -> tuple[list[Diagnostic], object | None]:
    try:
        program = ir.ast_to_ir(module)
        return [], program
    except Namel3ssError as err:
        code = "N3-1005"
        kwargs = {"field": "program", "kind": "module"}
        if "Duplicate" in err.message:
            code = "N3-1004"
            kwargs = {"name": err.message, "scope": "module"}
        diag = create_diagnostic(
            code,
            message_kwargs=kwargs,
            file=str(path),
            line=err.line,
            column=err.column,
            hint=err.message,
        )
        return [diag], None


def collect_diagnostics(paths: Iterable[Path], strict: bool) -> tuple[list[Diagnostic], dict]:
    ai_files = iter_ai_files(list(paths))
    all_diags: list[Diagnostic] = []
    if not ai_files:
        return [], {"errors": 0, "warnings": 0, "infos": 0}
    for path in ai_files:
        parse_diags, module = _parse_file(path)
        all_diags.extend(parse_diags)
        if module is None:
            continue
        ir_diags, program = _compile_to_ir(path, module)
        all_diags.extend(ir_diags)
        if program is None:
            continue
        legacy_diags = run_diagnostics(program, available_plugins=set())
        all_diags.extend(legacy_to_structured(d) for d in legacy_diags)

    all_diags, summary = apply_strict_mode(all_diags, strict)
    return all_diags, summary


def collect_lint(paths: Iterable[Path], config: linting.LintConfig | None = None) -> list[Diagnostic]:
    ai_files = iter_ai_files(list(paths))
    findings: list[Diagnostic] = []
    config = config or linting.LintConfig()
    for path in ai_files:
        parse_diags, module = _parse_file(path)
        findings.extend(parse_diags)
        if module is None:
            continue
        lint_results = linting.lint_module(module, file=str(path), config=config)
        findings.extend(f.to_diagnostic() for f in lint_results)
    return findings
