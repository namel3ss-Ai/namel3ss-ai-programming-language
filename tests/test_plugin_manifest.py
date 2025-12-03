import tempfile
from pathlib import Path

import pytest

from namel3ss.plugins.manifest import PluginManifest


def test_manifest_parses_valid_file():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "plugin.toml"
        path.write_text(
            """
id = "sample"
name = "Sample Plugin"
version = "0.1.0"
description = "demo"
author = "dev"
n3_core_version = ">=3.0.0,<4.0.0"

[entrypoints]
tools = "plugin_mod:register_tools"
""",
            encoding="utf-8",
        )
        manifest = PluginManifest.from_file(path)
        assert manifest.id == "sample"
        assert manifest.entrypoints["tools"] == "plugin_mod:register_tools"


def test_manifest_missing_fields_errors():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "plugin.toml"
        path.write_text("id = \"x\"\nname = \"x\"", encoding="utf-8")
        with pytest.raises(ValueError):
            PluginManifest.from_file(path)
