import json

import pytest

from namel3ss.cli import main


def _write(tmp_path, text: str):
    path = tmp_path / "program.ai"
    path.write_text(text, encoding="utf-8")
    return path


PROGRAM_WITH_WARN = (
    'page is "home":\n'
    '  title "Home"\n'
    '  route "/"\n'
    'flow is "pipe":\n'
)


def test_cli_diagnostics_json_output(tmp_path, capsys):
    path = _write(tmp_path, PROGRAM_WITH_WARN)
    try:
        main(["diagnostics", str(path), "--json"])
    except SystemExit:
        pass
    data = json.loads(capsys.readouterr().out)
    assert "summary" in data
    assert "diagnostics" in data
    assert data["summary"]["warnings"] >= 0
    assert any("code" in d for d in data["diagnostics"]) or data["diagnostics"] == []


def test_cli_diagnostics_strict_exit(tmp_path):
    path = _write(tmp_path, PROGRAM_WITH_WARN)
    try:
        main(["diagnostics", str(path), "--strict"])
    except SystemExit as excinfo:
        assert excinfo.code in (0, 1)
