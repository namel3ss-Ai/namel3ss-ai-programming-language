import json
from pathlib import Path

import pytest

from namel3ss.plugins.manifest import ManifestError, PluginManifest, load_manifest


def test_load_valid_manifest(tmp_path: Path):
    manifest = {
        "name": "demo-plugin",
        "version": "1.0.0",
        "description": "Demo",
        "entry_point": "demo:Plugin",
        "tags": ["demo"],
    }
    path = tmp_path / "plugin.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    loaded = load_manifest(path)
    assert loaded.name == "demo-plugin"
    assert loaded.entry_point == "demo:Plugin"


def test_missing_required_fields_raises(tmp_path: Path):
    manifest = {"name": "demo-plugin"}
    path = tmp_path / "plugin.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ManifestError):
        load_manifest(path)
