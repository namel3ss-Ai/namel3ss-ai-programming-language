from __future__ import annotations

import json
from pathlib import Path

import pytest

from namel3ss.cli import main


EXAMPLE_APP = """\
app "hello":
  entry_page "home"

page "home":
  route "/"
"""


def test_cli_bundle_creates_manifest_and_dockerfile(tmp_path: Path, monkeypatch):
    app_path = tmp_path / "app.ai"
    app_path.write_text(EXAMPLE_APP, encoding="utf-8")
    out_dir = tmp_path / "build"
    argv = ["bundle", str(app_path), "--output", str(out_dir), "--dockerfile", "--env", "FOO=BAR"]
    main(argv)
    bundle_root = out_dir / "hello"
    manifest_path = bundle_root / "manifest.json"
    assert manifest_path.exists()
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["app_name"] == "hello"
    assert data["env"]["FOO"] == "BAR"
    assert (bundle_root / "Dockerfile").exists()
