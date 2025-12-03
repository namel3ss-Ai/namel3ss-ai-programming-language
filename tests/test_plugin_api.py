import os
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from namel3ss.server import create_app


PLUGIN_TOML = """
id = "api-toolkit"
name = "API Toolkit"
version = "0.1.0"
description = "demo"
author = "dev"
n3_core_version = ">=3.0.0,<4.0.0"

[entrypoints]
tools = "api_toolkit:register_tools"
"""

PLUGIN_CODE = """
def register_tools(sdk):
    def echo(message: str):
        return f"echo:{message}"
    sdk.tools.register_tool("api_echo", echo, plugin_id="api-toolkit")
"""


def test_plugin_endpoints_list_and_load(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        plugin_dir = Path(tmp) / "api-toolkit"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.toml").write_text(PLUGIN_TOML, encoding="utf-8")
        (plugin_dir / "api_toolkit.py").write_text(PLUGIN_CODE, encoding="utf-8")
        monkeypatch.setenv("N3_PLUGINS_DIR", str(Path(tmp)))
        client = TestClient(create_app())
        res = client.get("/api/plugins", headers={"X-API-Key": "viewer-key"})
        assert res.status_code == 200
        assert any(p["id"] == "api-toolkit" for p in res.json()["plugins"])
        load = client.post("/api/plugins/api-toolkit/load", headers={"X-API-Key": "dev-key"})
        assert load.status_code == 200
        assert load.json()["plugin"]["loaded"] is True
