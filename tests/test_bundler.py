from __future__ import annotations

import json
from pathlib import Path

import pytest

from namel3ss.packaging.bundler import Bundler
from namel3ss.packaging.models import BundleManifest
from namel3ss.deploy.docker import generate_dockerfile


EXAMPLE_APP = """\
app "hello":
  entry_page "home"

page "home":
  route "/"
  section "hero":
    component "text":
      value "Welcome"
"""


def test_bundler_builds_manifest_and_files(tmp_path: Path):
    app_path = tmp_path / "app.ai"
    app_path.write_text(EXAMPLE_APP, encoding="utf-8")
    out = tmp_path / "dist"
    bundler = Bundler()
    bundle_root = bundler.build_bundle(app_path, target="server", output_dir=out, env={"FOO": "BAR"})
    manifest_path = bundle_root / "manifest.json"
    assert manifest_path.exists()
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = BundleManifest(**data)
    assert manifest.app_name == "hello"
    assert manifest.entrypoint in {"server_entry.py", "worker_entry.py", "server_entry.py"}
    assert manifest.env["FOO"] == "BAR"
    assert (bundle_root / "app.ai").exists()
    assert (bundle_root / manifest.entrypoint).exists()


def test_generate_dockerfile_includes_env_and_entrypoint():
    manifest = BundleManifest.from_bundle(
        app_name="hello",
        entrypoint="server_entry.py",
        bundle_type="server",
        env={"FOO": "BAR"},
        assets=[],
    )
    content = generate_dockerfile(manifest)
    assert "FROM python:3.11-slim" in content
    assert 'ENV FOO="BAR"' in content
    assert 'CMD ["python", "/app/server_entry.py"]' in content
