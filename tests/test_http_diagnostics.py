import json
from pathlib import Path

from fastapi.testclient import TestClient

from namel3ss.server import create_app


def _make_file(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_http_diagnostics_valid(tmp_path):
    client = TestClient(create_app())
    good = _make_file(tmp_path, "good.ai", 'app "a":\n  entry_page "home"\npage "home":\n  route "/"\n')
    resp = client.post(
        "/api/diagnostics",
        headers={"X-API-Key": "dev-key"},
        json={"paths": [str(good)], "strict": False, "summary_only": False},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["summary"]["errors"] == 0
    assert data["diagnostics"] == []


def test_http_diagnostics_invalid_codes(tmp_path):
    client = TestClient(create_app())
    bad = _make_file(tmp_path, "bad.ai", 'page "p":\n  title "T"\n')
    resp = client.post(
        "/api/diagnostics",
        headers={"X-API-Key": "dev-key"},
        json={"paths": [str(bad)], "strict": False, "summary_only": False},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    codes = {d["code"] for d in data["diagnostics"]}
    assert {"N3-1001", "N3-1005"} & codes
    assert data["summary"]["errors"] >= 1


def test_http_diagnostics_strict(tmp_path):
    client = TestClient(create_app())
    warn_file = _make_file(tmp_path, "warn.ai", 'flow "pipeline":\n')
    resp = client.post(
        "/api/diagnostics",
        headers={"X-API-Key": "dev-key"},
        json={"paths": [str(warn_file)], "strict": False, "summary_only": False},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    resp_strict = client.post(
        "/api/diagnostics",
        headers={"X-API-Key": "dev-key"},
        json={"paths": [str(warn_file)], "strict": True, "summary_only": False},
    )
    strict_data = resp_strict.json()
    assert strict_data["summary"]["errors"] >= data["summary"]["errors"]
    assert strict_data["success"] is False


def test_http_diagnostics_summary_only(tmp_path):
    client = TestClient(create_app())
    path = _make_file(tmp_path, "good.ai", 'app "a":\n  entry_page "home"\npage "home":\n  route "/"\n')
    resp = client.post(
        "/api/diagnostics",
        headers={"X-API-Key": "dev-key"},
        json={"paths": [str(path)], "strict": False, "summary_only": True},
    )
    data = resp.json()
    assert data["diagnostics"] == []
    assert data["summary"]["errors"] == 0


def test_http_diagnostics_directory(tmp_path):
    client = TestClient(create_app())
    _make_file(tmp_path, "good.ai", 'app "a":\n  entry_page "home"\npage "home":\n  route "/"\n')
    _make_file(tmp_path, "bad.ai", 'page "p":\n')
    resp = client.post(
        "/api/diagnostics",
        headers={"X-API-Key": "dev-key"},
        json={"paths": [str(tmp_path)], "strict": False, "summary_only": False},
    )
    data = resp.json()
    assert data["summary"]["errors"] >= 1
    files = {d["file"] for d in data["diagnostics"]}
    assert any("bad.ai" in f for f in files)
