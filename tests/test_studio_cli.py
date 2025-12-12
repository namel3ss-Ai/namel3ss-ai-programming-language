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
    (tmp_path / "app.ai").write_text("flow \"x\":\n  step \"s\":\n    log info \"hi\"", encoding="utf-8")
    assert cli.detect_project_root(tmp_path) == tmp_path


def test_run_studio_invokes_servers(monkeypatch, tmp_path, capsys):
    (tmp_path / "demo.ai").write_text("flow \"x\":\n  step \"s\":\n    log info \"hi\"", encoding="utf-8")

    called = {"backend": False, "stop": False, "browser": False}

    class DummyProc:
        def terminate(self):
            called["backend"] = True

        def is_alive(self):
            return True

        def join(self, timeout=None):
            called["stop"] = True

    def fake_start_daemon(*args, **kwargs):
        called["backend"] = True
        return DummyProc()

    monkeypatch.setattr(cli, "start_daemon_process", fake_start_daemon)
    monkeypatch.setattr(cli, "_wait_for_http", lambda *args, **kwargs: (True, None))
    monkeypatch.setattr(cli, "_fetch_studio_status", lambda *args, **kwargs: ({"studio_static_available": True}, None))
    monkeypatch.setattr(cli, "_studio_status_messages", lambda status: ["ok"])
    monkeypatch.setattr(cli, "_stop_process", lambda *args, **kwargs: called.update(stop=True))
    monkeypatch.setattr(cli.webbrowser, "open", lambda url: called.update(browser=True))

    cli.run_studio(backend_port=8100, ui_port=4200, open_browser=False, project_root=tmp_path, block=False)
    out = capsys.readouterr().out
    assert "Studio URL" in out
    assert called["backend"] is True
    assert called["stop"] is True
    assert called["browser"] is False


def test_run_studio_invalid_project(tmp_path):
    with pytest.raises(SystemExit):
        cli.run_studio(project_root=tmp_path, open_browser=False, block=False)
