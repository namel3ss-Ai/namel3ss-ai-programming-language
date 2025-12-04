import json

import pytest

from namel3ss.cli import main


def _write(tmp_path, text: str):
    path = tmp_path / "program.ai"
    path.write_text(text, encoding="utf-8")
    return path


PROGRAM_WITH_WARN = (
    'page "home":\n'
    '  title "Home"\n'
    '  route "/"\n'
    'flow "pipe":\n'
)


def test_cli_diagnostics_json_output(tmp_path, capsys):
    path = _write(tmp_path, PROGRAM_WITH_WARN)
    main(["diagnostics", str(path), "--json"])
    data = json.loads(capsys.readouterr().out)
    assert "summary" in data
    assert "diagnostics" in data
    assert data["summary"]["warnings"] >= 1
    assert any("code" in d for d in data["diagnostics"])


def test_cli_diagnostics_strict_exit(tmp_path):
    path = _write(tmp_path, PROGRAM_WITH_WARN)
    with pytest.raises(SystemExit) as excinfo:
        main(["diagnostics", str(path), "--strict"])
    assert excinfo.value.code == 1
