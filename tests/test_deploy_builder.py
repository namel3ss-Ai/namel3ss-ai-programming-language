import zipfile
import tempfile
from pathlib import Path

from namel3ss.deploy.builder import DeployBuilder
from namel3ss.deploy.models import DeployTargetConfig, DeployTargetKind


SOURCE = 'app "demo":\n  entry_page "home"\n'


def test_build_server_and_worker():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        builder = DeployBuilder(SOURCE, out)
        targets = [
            DeployTargetConfig(kind=DeployTargetKind.SERVER, name="server", output_dir=out / "server"),
            DeployTargetConfig(kind=DeployTargetKind.WORKER, name="worker", output_dir=out / "worker"),
            DeployTargetConfig(kind=DeployTargetKind.DOCKER, name="docker", output_dir=out / "docker"),
        ]
        artifacts = builder.build(targets)
        assert (out / "server" / "server_entry.py").exists()
        assert (out / "worker" / "worker_entry.py").exists()
        assert (out / "docker" / "Dockerfile.server").exists()
        assert len(artifacts) == 3


def test_build_lambda_creates_zip():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        builder = DeployBuilder(SOURCE, out)
        target = DeployTargetConfig(kind=DeployTargetKind.SERVERLESS_AWS, name="lambda", output_dir=out / "lambda")
        artifacts = builder.build([target])
        bundle = artifacts[0].path
        assert bundle.exists()
        with zipfile.ZipFile(bundle) as zf:
            names = zf.namelist()
            assert "aws_lambda.py" in names
            assert "app.ai" in names


def test_build_desktop_mobile_templates():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        builder = DeployBuilder(SOURCE, out)
        desktop_target = DeployTargetConfig(kind=DeployTargetKind.DESKTOP, name="desktop", output_dir=out / "desktop")
        mobile_target = DeployTargetConfig(kind=DeployTargetKind.MOBILE, name="mobile", output_dir=out / "mobile")
        builder.build([desktop_target, mobile_target])
        assert (out / "desktop" / "README.md").exists()
        assert (out / "mobile" / "App.tsx").exists()
