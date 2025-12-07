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


def test_code_transform_label(tmp_path: Path):
    (tmp_path / "pages").mkdir()
    (tmp_path / "pages" / "home.ai").write_text('page "home" at "/":\n  heading "Welcome"\n', encoding="utf-8")
    client = _client(tmp_path)
    manifest = client.get("/api/ui/manifest", headers={"X-API-Key": "dev-key"}).json()
    heading = manifest["pages"][0]["layout"][0]
    resp = client.post(
        "/api/studio/code/transform",
        headers={"X-API-Key": "dev-key"},
        json={"path": "pages/home.ai", "element_id": heading["id"], "property": "text", "new_value": "Hello"},
    )
    assert resp.status_code == 200
    updated = (tmp_path / "pages" / "home.ai").read_text(encoding="utf-8")
    assert '"Hello"' in updated


def test_code_transform_missing_element(tmp_path: Path):
    (tmp_path / "pages").mkdir()
    (tmp_path / "pages" / "home.ai").write_text('page "home" at "/":\n  heading "Welcome"\n', encoding="utf-8")
    client = _client(tmp_path)
    resp = client.post(
        "/api/studio/code/transform",
        headers={"X-API-Key": "dev-key"},
        json={"path": "pages/home.ai", "element_id": "bad", "property": "text", "new_value": "Hello"},
    )
    assert resp.status_code == 404


def test_code_transform_insert_delete_move(tmp_path: Path):
    (tmp_path / "pages").mkdir()
    (tmp_path / "pages" / "home.ai").write_text('page "home" at "/":\n  heading "One"\n  heading "Two"\n', encoding="utf-8")
    client = _client(tmp_path)
    manifest = client.get("/api/ui/manifest", headers={"X-API-Key": "dev-key"}).json()
    first = manifest["pages"][0]["layout"][0]
    # insert after first
    resp = client.post(
        "/api/studio/code/transform",
        headers={"X-API-Key": "dev-key"},
        json={
            "op": "insert_element",
            "path": "pages/home.ai",
            "element_id": first["id"],
            "position": "after",
            "new_element": {"type": "heading", "properties": {"label": "Inserted"}},
        },
    )
    assert resp.status_code == 200
    content = (tmp_path / "pages" / "home.ai").read_text(encoding="utf-8")
    assert 'heading "Inserted"' in content
    # move down newly inserted element (roughly)
    manifest = client.get("/api/ui/manifest", headers={"X-API-Key": "dev-key"}).json()
    btn = next(l for l in manifest["pages"][0]["layout"] if l.get("text") == "Inserted")
    resp = client.post(
        "/api/studio/code/transform",
        headers={"X-API-Key": "dev-key"},
        json={"op": "move_element", "path": "pages/home.ai", "element_id": btn["id"], "position": "up"},
    )
    assert resp.status_code == 200
    # delete
    resp = client.post(
        "/api/studio/code/transform",
        headers={"X-API-Key": "dev-key"},
        json={"op": "delete_element", "path": "pages/home.ai", "element_id": btn["id"]},
    )
    assert resp.status_code == 200
    content = (tmp_path / "pages" / "home.ai").read_text(encoding="utf-8")
    assert 'heading "Inserted"' not in content
