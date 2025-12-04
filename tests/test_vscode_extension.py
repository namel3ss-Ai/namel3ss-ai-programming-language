import json
from pathlib import Path


def test_vscode_extension_manifest_valid():
    pkg_path = Path("vscode-extension/package.json")
    data = json.loads(pkg_path.read_text(encoding="utf-8"))
    assert data["contributes"]["languages"][0]["id"] == "namel3ss"
    commands = {c["command"] for c in data["contributes"]["commands"]}
    assert "namel3ss.restartServer" in commands
    config = data["contributes"]["configuration"]["properties"]
    assert "namel3ss.lsp.command" in config
