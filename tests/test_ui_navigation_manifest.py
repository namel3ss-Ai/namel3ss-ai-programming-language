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


def test_manifest_includes_navigation_route(tmp_path: Path):
    (tmp_path / "pages").mkdir()
    (tmp_path / "pages" / "home.ai").write_text(
        'page "home" at "/":\n'
        '  button "Go":\n'
        '    on click:\n'
        '      go to page "dashboard"\n',
        encoding="utf-8",
    )
    (tmp_path / "pages" / "dashboard.ai").write_text('page "dashboard" at "/dashboard":\n  heading "Dash"\n', encoding="utf-8")
    client = _client(tmp_path)
    resp = client.get("/api/ui/manifest", headers={"X-API-Key": "dev-key"})
    assert resp.status_code == 200
    data = resp.json()
    home = next(p for p in data["pages"] if p["name"] == "home")
    btn = next(el for el in home["layout"] if el["type"] == "button")
    nav = next(a for a in btn["actions"] if a["kind"] == "goto_page")
    assert nav["route"] == "/dashboard"
