from __future__ import annotations

import json
from pathlib import Path

from namel3ss.cli import main


APP = """\
app "desk":
  entry_page "home"

page "home":
  route "/"
"""


def test_cli_desktop_prepares_bundle(tmp_path: Path, capsys):
    app = tmp_path / "app.ai"
    app.write_text(APP, encoding="utf-8")
    out = tmp_path / "desktop-out"
    main(["desktop", str(app), "--output", str(out), "--no-build-tauri"])
    bundle_root = out / "desk"
    manifest = json.loads((bundle_root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["bundle_type"] == "desktop"
    assert (bundle_root / "tauri.conf.json").exists()
