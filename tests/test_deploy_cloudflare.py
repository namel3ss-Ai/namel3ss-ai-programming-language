from pathlib import Path

from namel3ss.deploy.builder import DeployBuilder
from namel3ss.deploy.models import DeployTargetConfig, DeployTargetKind


def test_build_cloudflare_creates_bundle(tmp_path: Path):
    source = 'app "demo" version "0.0.1"\nflow "hello":\n  return "hi"\n'
    builder = DeployBuilder(source, tmp_path)
    out_dir = tmp_path / "cloudflare"
    target = DeployTargetConfig(kind=DeployTargetKind.SERVERLESS_CLOUDFLARE, name="cf", output_dir=out_dir)
    artifacts = builder.build([target])
    assert artifacts, "No artifacts returned"
    artifact = artifacts[0]
    assert artifact.kind == DeployTargetKind.SERVERLESS_CLOUDFLARE
    assert (out_dir / "app.ai").exists()
    worker = out_dir / "worker.js"
    wrangler = out_dir / "wrangler.toml"
    readme = out_dir / "README.md"
    assert worker.exists()
    assert wrangler.exists()
    assert readme.exists()
    content = worker.read_text(encoding="utf-8")
    assert "fetch(request" in content
    toml = wrangler.read_text(encoding="utf-8")
    assert 'main = "worker.js"' in toml
    assert "compatibility_date" in toml
