from fastapi.testclient import TestClient
import pytest

from namel3ss.server import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("N3_OPTIMIZER_DB", str(tmp_path / "opt.db"))
    monkeypatch.setenv("N3_OPTIMIZER_OVERLAYS", str(tmp_path / "overlays.json"))
    return TestClient(create_app())


def test_fmt_preview_changes_code(client: TestClient):
    source = (
        'app "demo":\n'
        "    entry_page \"home\"\n"
        "\n"
        'page "home":\n'
        '    route "/"\n'
        '    section "main":\n'
        '        component "text":\n'
        '            value "Hello"\n'
    )
    resp = client.post("/api/fmt/preview", json={"source": source})
    assert resp.status_code == 200
    data = resp.json()
    assert data["formatted"] != source
    assert data["changes_made"] is True


def test_fmt_preview_no_changes_for_formatted_code(client: TestClient):
    source = (
        'app "demo":\n'
        '  entry_page "home"\n'
        "\n"
        'page "home":\n'
        '  route "/"\n'
        '  section "main":\n'
        '    component "text":\n'
        '      value "Hello"\n'
    )
    resp = client.post("/api/fmt/preview", json={"source": source})
    assert resp.status_code == 200
    data = resp.json()
    assert data["formatted"] == source
    assert data["changes_made"] is False


def test_fmt_preview_empty_source(client: TestClient):
    resp = client.post("/api/fmt/preview", json={"source": ""})
    assert resp.status_code == 200
    data = resp.json()
    assert data["formatted"] == ""
    assert data["changes_made"] is False


def test_fmt_preview_handles_invalid_code_gracefully(client: TestClient):
    resp = client.post("/api/fmt/preview", json={"source": 'app "broken"'})
    assert resp.status_code == 400
    body = resp.json()
    assert "detail" in body
