import json
from pathlib import Path

from namel3ss.plugins.registry import PluginRegistry


def test_registry_discovers_plugins(tmp_path: Path):
    pdir = tmp_path / "plugins"
    pdir.mkdir()
    (pdir / "a").mkdir()
    manifest = {
        "name": "plugin-a",
        "version": "0.1.0",
        "description": "A",
        "entry_point": "demo:Plugin",
        "tags": ["tag"],
    }
    (pdir / "a" / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")
    registry = PluginRegistry(builtins_dir=tmp_path / "none", user_dir=pdir)
    plugins = registry.list_plugins()
    assert any(p.name == "plugin-a" for p in plugins)
