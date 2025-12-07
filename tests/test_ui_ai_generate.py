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


def test_ai_generate_ui_inserts_content(tmp_path: Path):
    (tmp_path / "pages").mkdir()
    (tmp_path / "pages" / "home.ai").write_text('page "home" at "/":\n  heading "Welcome"\n', encoding="utf-8")
    client = _client(tmp_path)
    resp = client.post(
        "/api/studio/ui/generate",
        headers={"X-API-Key": "dev-key"},
        json={"prompt": "Add a greeting", "page_path": "pages/home.ai"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("success") is True
    content = (tmp_path / "pages" / "home.ai").read_text(encoding="utf-8")
    assert 'heading "AI Generated"' in content
    assert 'Add a greeting' in content
