from pathlib import Path

from fastapi.testclient import TestClient

from namel3ss.server import create_app


def _client(tmp_path: Path) -> TestClient:
    import os

    prev = os.getcwd()
    os.chdir(tmp_path)
    try:
        return TestClient(create_app())
    finally:
        os.chdir(prev)


def test_ui_manifest_endpoint(tmp_path: Path):
    (tmp_path / "pages").mkdir()
    (tmp_path / "pages" / "home.ai").write_text(
        'page "home" at "/":\n  heading "Welcome"\n  text "Hello"\n', encoding="utf-8"
    )
    client = _client(tmp_path)
    resp = client.get("/api/ui/manifest", headers={"X-API-Key": "dev-key"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ui_manifest_version"] == "1"
    assert data["pages"]
    page = data["pages"][0]
    assert page["name"] == "home"
    assert page["layout"][0]["type"] == "heading"
    assert "id" in page["layout"][0]
