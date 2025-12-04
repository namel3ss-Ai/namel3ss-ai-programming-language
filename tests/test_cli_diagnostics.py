import json
from pathlib import Path

import pytest

from namel3ss import cli


def run_cli(args, tmp_path):
    try:
        cli.main(args)
        return 0, ""
    except SystemExit as exc:
        return exc.code or 0, ""


def test_diagnostics_valid_file(tmp_path, capsys):
    src = tmp_path / "valid.ai"
    src.write_text('app "a":\n  entry_page "home"\npage "home":\n  route "/"\n', encoding="utf-8")
    cli.main(["diagnostics", str(src)])
    out = capsys.readouterr().out
    assert "Summary:" in out
    assert "0 errors" in out


def test_diagnostics_invalid_file_json(tmp_path, capsys):
    src = tmp_path / "invalid.ai"
    src.write_text('app "a":\n  entry_page "home"\npage "home":\n  title "Home"\n', encoding="utf-8")
    with pytest.raises(SystemExit):
        cli.main(["diagnostics", str(src), "--json"])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["success"] is False
    codes = {d["code"] for d in payload["diagnostics"]}
    assert "N3-1001" in codes


def test_diagnostics_strict_mode_upgrades_warning(tmp_path, capsys):
    src = tmp_path / "flow.ai"
    src.write_text('flow "pipeline":\n', encoding="utf-8")
    # non-strict should succeed
    exit_code, _ = run_cli(["diagnostics", str(src)], tmp_path)
    assert exit_code == 0
    # strict should fail
    with pytest.raises(SystemExit):
        cli.main(["diagnostics", str(src), "--strict"])
    out = capsys.readouterr().out
    assert "errors" in out


def test_diagnostics_summary_only(tmp_path, capsys):
    src = tmp_path / "valid.ai"
    src.write_text('app "a":\n  entry_page "home"\npage "home":\n  route "/"\n', encoding="utf-8")
    cli.main(["diagnostics", str(src), "--summary-only"])
    out = capsys.readouterr().out.strip()
    assert out.startswith("Summary:")
    assert "errors" in out and "warnings" in out


def test_diagnostics_directory_multiple_files(tmp_path, capsys):
    good = tmp_path / "good.ai"
    bad = tmp_path / "bad.ai"
    good.write_text('app "a":\n  entry_page "home"\npage "home":\n  route "/"\n', encoding="utf-8")
    bad.write_text('page "p":\n', encoding="utf-8")
    with pytest.raises(SystemExit):
        cli.main(["diagnostics", str(tmp_path), "--json"])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["summary"]["errors"] >= 1
    files = {d.get("file") for d in payload["diagnostics"]}
    assert str(bad) in files or str(bad.resolve()) in files
