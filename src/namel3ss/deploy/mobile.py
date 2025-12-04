from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

from namel3ss.packaging.models import BundleManifest


def generate_mobile_config(manifest: BundleManifest, port: int = 8000) -> Dict:
    """
    Build a mobile configuration snippet from a bundle manifest.
    """
    base_url = manifest.metadata.get("base_url") or f"http://127.0.0.1:{port}"
    return {
        "appName": manifest.app_name,
        "defaultBaseUrl": base_url,
        "apiPrefix": "/api",
        "bundleType": manifest.bundle_type,
    }


def write_mobile_config(config: Dict, dest: Path) -> None:
    dest.write_text(json.dumps(config, indent=2), encoding="utf-8")
