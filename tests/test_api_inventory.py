from namel3ss.api_inventory import list_cli_commands, list_http_routes
from namel3ss.server import create_app


def test_cli_inventory_contains_core_commands():
    commands = set(list_cli_commands())
    expected = {
        "parse",
        "ir",
        "run",
        "graph",
        "serve",
        "run-agent",
        "run-flow",
        "page-ui",
        "meta",
        "job-flow",
        "job-agent",
        "job-status",
        "diagnostics",
        "bundle",
        "build-target",
        "optimize",
        "test-cov",
        "init",
    }
    assert expected.issubset(commands)


def test_http_inventory_lists_key_endpoints(tmp_path, monkeypatch):
    monkeypatch.setenv("N3_OPTIMIZER_DB", str(tmp_path / "opt.db"))
    monkeypatch.setenv("N3_OPTIMIZER_OVERLAYS", str(tmp_path / "overlays.json"))
    app = create_app()
    routes = set(list_http_routes(app))
    required = {
        ("POST", "/api/run-flow"),
        ("POST", "/api/run-app"),
        ("POST", "/api/flows"),
        ("GET", "/api/plugins"),
        ("POST", "/api/optimizer/scan"),
        ("GET", "/api/optimizer/suggestions"),
        ("POST", "/api/flows/triggers"),
    }
    assert required.issubset(routes)
