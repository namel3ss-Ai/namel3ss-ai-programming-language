from pathlib import Path

import pytest
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


def test_studio_files_tree(monkeypatch, tmp_path: Path):
    (tmp_path / "pages").mkdir()
    (tmp_path / "flows").mkdir()
    (tmp_path / "pages" / "home.ai").write_text('page "home":\n  heading "Hi"\n', encoding="utf-8")
    (tmp_path / "flows" / "run.ai").write_text('flow "run":\n  step "s":\n    log info "ok"\n', encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "ignore.ai").write_text("", encoding="utf-8")

    client = _client(tmp_path)
    resp = client.get("/api/studio/files", headers={"X-API-Key": "dev-key"})
    assert resp.status_code == 200
    root = resp.json()["root"]
    assert root["type"] == "directory"
    names = {c["name"] for c in root["children"]}
    assert "pages" in names
    assert "flows" in names
    assert ".git" not in names
    pages = next(c for c in root["children"] if c["name"] == "pages")
    page_file = pages["children"][0]
    assert page_file["path"] == "pages/home.ai"
    assert page_file["kind"] == "page"


def test_studio_file_path_traversal(tmp_path: Path):
    (tmp_path / "main.ai").write_text('flow "x":\n  step "s":\n    log info "ok"\n', encoding="utf-8")
    client = _client(tmp_path)
    resp = client.get("/api/studio/file", params={"path": "../outside.ai"}, headers={"X-API-Key": "dev-key"})
    assert resp.status_code == 400
