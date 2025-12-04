from pathlib import Path

import pytest

from namel3ss.cli import main


def test_cli_create_basic(tmp_path: Path, monkeypatch):
    cwd = tmp_path
    monkeypatch.chdir(cwd)
    main(["create", "demo-app"])
    target = cwd / "demo-app"
    assert target.exists()
    assert (target / "app.ai").exists()
    assert (target / "README.md").exists()


def test_cli_create_list_templates(capsys):
    main(["create", "--list-templates"])
    out = capsys.readouterr().out
    assert "app-basic" in out


def test_cli_create_template_flag(tmp_path: Path, monkeypatch):
    cwd = tmp_path
    monkeypatch.chdir(cwd)
    main(["create", "demo-rag", "--template", "app-rag"])
    content = (cwd / "demo-rag" / "app.ai").read_text(encoding="utf-8")
    assert "file-upload" in content


def test_cli_create_refuse_overwrite(tmp_path: Path, monkeypatch):
    cwd = tmp_path
    monkeypatch.chdir(cwd)
    target = cwd / "demo"
    target.mkdir()
    (target / "existing.txt").write_text("hi", encoding="utf-8")
    with pytest.raises(SystemExit):
        main(["create", "demo"])


def test_cli_create_force_overwrite(tmp_path: Path, monkeypatch):
    cwd = tmp_path
    monkeypatch.chdir(cwd)
    target = cwd / "demo"
    target.mkdir()
    (target / "existing.txt").write_text("hi", encoding="utf-8")
    main(["create", "demo", "--force"])
    assert (target / "app.ai").exists()
