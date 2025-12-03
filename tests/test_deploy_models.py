from pathlib import Path

from namel3ss.deploy.models import BuildArtifact, DeployTargetConfig, DeployTargetKind


def test_target_config_and_artifact():
    cfg = DeployTargetConfig(kind=DeployTargetKind.SERVER, name="srv", output_dir=Path("/tmp/out"))
    art = BuildArtifact(kind=DeployTargetKind.SERVER, path=Path("/tmp/out/server_entry.py"), metadata={"entrypoint": "x"})
    assert cfg.kind == DeployTargetKind.SERVER
    assert art.metadata["entrypoint"] == "x"
