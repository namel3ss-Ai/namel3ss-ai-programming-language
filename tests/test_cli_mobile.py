from __future__ import annotations

import json
from pathlib import Path

from namel3ss.cli import main

APP = """\
app "mobileapp":
  entry_page "home"

page "home":
  route "/"
"""


def test_cli_mobile_generates_config(tmp_path: Path):
    app = tmp_path / "app.ai"
    app.write_text(APP, encoding="utf-8")
    out = tmp_path / "mobile-out"
    main(["mobile", str(app), "--output", str(out), "--no-expo-scaffold"])
    config_path = out / "namel3ss.config.json"
    assert config_path.exists()
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    assert cfg["appName"] == "mobileapp"
    assert cfg["defaultBaseUrl"].startswith("http://127.0.0.1")

