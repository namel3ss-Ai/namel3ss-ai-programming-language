from pathlib import Path

from namel3ss.cli import main


def test_cli_migrate_data_pipelines(tmp_path, capsys):
    sample = tmp_path / "sample.ai"
    sample.write_text(
        'flow is "f":\n'
        '  step is "s":\n'
        "    all item from xs where item > 0\n",
        encoding="utf-8",
    )
    # Dry run should not change the file
    main(["migrate", "data-pipelines", str(sample)])
    out = capsys.readouterr().out
    assert "Dry run" in out
    assert "legacy" in out.lower()
    assert "keep rows where" not in sample.read_text(encoding="utf-8")

    # Apply changes
    main(["migrate", "data-pipelines", "--write", str(sample)])
    updated = sample.read_text(encoding="utf-8")
    assert "keep rows where" in updated
    assert "let filtered_rows be xs:" in updated
