import builtins
from pathlib import Path

import pytest

from namel3ss import cli


def test_studio_args_parsing():
    parser = cli.build_cli_parser()
    args = parser.parse_args(["studio", "--backend-port", "9001", "--ui-port", "5001", "--no-open-browser"])
    assert args.command == "studio"
    assert args.backend_port == 9001
    assert args.ui_port == 5001
    assert args.no_open_browser is True


def test_detect_project_root(tmp_path: Path):
    assert cli.detect_project_root(tmp_path) is None
    (tmp_path / "app.ai").write_text("flow \"x\":\n  step \"s\":\n    log info \"hi\"", encoding="utf-8")
    assert cli.detect_project_root(tmp_path) == tmp_path


def test_run_studio_invokes_servers(monkeypatch, tmp_path, capsys):
    (tmp_path / "demo.ai").write_text("flow \"x\":\n  step \"s\":\n    log info \"hi\"", encoding="utf-8")

    called = {"backend": False, "ui": False, "browser": False}

    class DummyProc:
        def terminate(self):
            called["backend"] = True

    class DummyServer:
        def shutdown(self):
            called["ui"] = True

    monkeypatch.setattr(cli, "start_backend_process", lambda port: DummyProc())
    monkeypatch.setattr(cli, "start_ui_server", lambda port: (DummyServer(), None))
    monkeypatch.setattr(cli.webbrowser, "open", lambda url: called.update(browser=True))

    cli.run_studio(backend_port=8100, ui_port=4200, open_browser=False, project_root=tmp_path, block=False)
    out = capsys.readouterr().out
    assert "http://namel3ss.local/studio" in out
    assert "http://127.0.0.1:4200/studio" in out
    assert called["ui"] is True
    assert called["backend"] is True
    assert called["browser"] is False


def test_run_studio_invalid_project(tmp_path):
    with pytest.raises(SystemExit):
        cli.run_studio(project_root=tmp_path, open_browser=False, block=False)


def test_studio_html_structure():
    html = cli._StudioHandler.html
    assert "Namel3ss Studio" in html
    assert "studio-topbar" in html
    assert "Project" in html
    assert "project-refresh" in html
    assert "code-editor" in html
    assert "ui-preview" in html
    assert "device-desktop" in html
    assert "mode-preview" in html
    assert "main-tab" in html
    assert "Inspector" in html
    assert "statusbar" in html
