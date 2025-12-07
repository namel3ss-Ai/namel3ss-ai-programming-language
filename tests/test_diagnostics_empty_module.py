from pathlib import Path

from namel3ss.diagnostics.runner import collect_diagnostics


def test_empty_file_produces_error(tmp_path: Path):
    path = tmp_path / "empty.ai"
    path.write_text("", encoding="utf-8")
    diags, summary = collect_diagnostics([path], strict=False)
    assert summary["errors"] >= 1
    codes = {d.code for d in diags}
    assert "N3-1010" in codes
