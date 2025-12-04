from __future__ import annotations

from namel3ss.deploy.mobile import generate_mobile_config
from namel3ss.packaging.models import BundleManifest


def test_generate_mobile_config_from_manifest():
    manifest = BundleManifest.from_bundle(
        app_name="hello",
        entrypoint="server_entry.py",
        bundle_type="server",
        env={},
        metadata={"base_url": "http://localhost:9000"},
    )
    config = generate_mobile_config(manifest, port=8123)
    assert config["appName"] == "hello"
    assert config["defaultBaseUrl"] == "http://localhost:9000"
    assert config["apiPrefix"] == "/api"

