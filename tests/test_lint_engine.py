from pathlib import Path

import pytest

from namel3ss.linting import LintConfig, lint_source
from namel3ss.cli import main


def test_lint_unused_and_shadowed(tmp_path: Path):
    source = (
        'flow "demo":\n'
        '  step "s":\n'
        '    let x = 1\n'
        '    let x = 2\n'
        '    do tool "echo"\n'
    )
    findings = lint_source(source, file="demo.ai")
    codes = {f.rule_id for f in findings}
    assert "N3-L001" in codes  # unused
    assert "N3-L005" in codes  # shadowed


def test_lint_config_disables_rule():
    source = (
        'flow "demo":\n'
        '  step "s":\n'
        '    let y = 1\n'
        '    do tool "echo"\n'
    )
    cfg = LintConfig(rule_levels={"N3-L001": "off"})
    findings = lint_source(source, file="demo.ai", config=cfg)
    assert not any(f.rule_id == "N3-L001" for f in findings)


def test_cli_lint_outputs_findings(tmp_path: Path, capsys):
    program_file = tmp_path / "lint.ai"
    program_file.write_text('flow "demo":\n  step "s":\n    let temp = 1\n', encoding="utf-8")
    main(["lint", str(program_file)])
    out = capsys.readouterr().out
    assert "N3-L001" in out
    assert "N3-L007" in out
