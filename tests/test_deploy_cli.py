import json
import tempfile
from pathlib import Path

from namel3ss.cli import main


def test_cli_build_target_server(capsys):
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "app.ai"
        source.write_text('app "demo":\n  entry_page "home"\n', encoding="utf-8")
        out_dir = Path(tmp) / "build"
        main(["build-target", "server", "--file", str(source), "--output-dir", str(out_dir)])
        captured = capsys.readouterr().out
        payload = json.loads(captured)
        assert payload["artifacts"][0]["kind"] == "DeployTargetKind.SERVER" or payload["artifacts"][0]["kind"] == "DeployTargetKind.SERVER".replace("DeployTargetKind.", "")
        assert (out_dir / "server_entry.py").exists()
