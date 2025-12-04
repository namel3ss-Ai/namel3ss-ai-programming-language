from __future__ import annotations

import json
from pathlib import Path

from namel3ss.packaging.bundler import Bundler
from namel3ss.deploy.desktop import generate_tauri_config


APP = """\
app "desk":
  entry_page "home"

page "home":
  route "/"
"""


def test_desktop_bundle_generates_manifest_and_tauri(tmp_path: Path):
    app = tmp_path / "app.ai"
    app.write_text(APP, encoding="utf-8")
    out = tmp_path / "out"
    bundler = Bundler()
    bundle_root = bundler.build_bundle(app, target="desktop", output_dir=out, env={"PORT": "8123"})
    manifest_path = bundle_root / "manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["bundle_type"] == "desktop"
    config = generate_tauri_config(type("obj", (), manifest), port=8123)  # simple duck-type
    assert config["build"]["devPath"] == "http://127.0.0.1:8123"
    assert "windows" in config["tauri"]
