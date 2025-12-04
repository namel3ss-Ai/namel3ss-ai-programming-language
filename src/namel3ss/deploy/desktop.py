from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

from namel3ss.packaging.models import BundleManifest


def generate_tauri_config(manifest: BundleManifest, port: int = 8000) -> Dict:
    """
    Build a minimal tauri.conf.json structure that starts the bundled server and points the webview at Studio.
    """
    server_cmd = ["python", f"/app/{manifest.entrypoint}"]
    if manifest.metadata.get("bundle_type") == "desktop":
        # allow overriding entry if provided in metadata
        custom_cmd = manifest.metadata.get("desktop_command")
        if custom_cmd:
            server_cmd = custom_cmd
    return {
        "package": {
            "productName": manifest.app_name or "Namel3ss",
            "version": manifest.version,
        },
        "build": {
            "beforeDevCommand": " ".join(server_cmd),
            "beforeBuildCommand": " ".join(server_cmd),
            "devPath": f"http://127.0.0.1:{port}",
            "distDir": "../static" if manifest.assets else ".",
        },
        "tauri": {
            "bundle": {"active": False},
            "windows": [
                {"title": manifest.app_name or "Namel3ss Studio", "width": 1280, "height": 800, "resizable": True}
            ],
            "allowlist": {"http": {"scope": ["http://127.0.0.1:*"]}},
        },
    }


def write_tauri_config(config: Dict, dest: Path) -> None:
    dest.write_text(json.dumps(config, indent=2), encoding="utf-8")
