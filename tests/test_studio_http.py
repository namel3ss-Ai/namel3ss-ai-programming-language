import json
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from namel3ss.server import create_app


def _client():
    return TestClient(create_app())


def test_studio_page_served():
    client = _client()
    resp = client.get("/studio")
    assert resp.status_code == 200
    assert "<title" in resp.text
    assert "Namel3ss Studio" in resp.text


def test_studio_static_assets_served():
    client = _client()
    css = client.get("/studio-static/studio.css")
    js = client.get("/studio-static/studio.js")
    assert css.status_code == 200
    assert "body" in css.text
    assert js.status_code == 200
    assert "studio" in js.text.lower()


def _assert_json_response(path: str, method: str = "GET", payload=None, headers=None, ok_status=(200,)):
    client = _client()
    if method == "GET":
        resp = client.get(path, headers=headers or {})
    else:
        resp = client.post(path, json=payload or {}, headers=headers or {})
    assert resp.status_code in ok_status
    if resp.status_code == 200:
        json.loads(resp.text)
    return resp


def test_studio_summary_endpoint():
    _assert_json_response("/api/studio-summary", headers={"X-API-Key": "viewer-key"})


def test_last_trace_endpoint_reachable():
    resp = _assert_json_response("/api/last-trace", headers={"X-API-Key": "dev-key"}, ok_status=(200, 404))
    if resp.status_code == 200:
        assert "trace" in resp.json()


def test_diagnostics_endpoint_reachable(tmp_path: Path):
    sample = 'page "home":\n  title "Home"\n'
    sample_file = tmp_path / "program.ai"
    sample_file.write_text(sample, encoding="utf-8")
    payload = {"paths": [str(sample_file)], "strict": False, "summary_only": True}
    _assert_json_response("/api/diagnostics", method="POST", payload=payload, headers={"X-API-Key": "dev-key"}, ok_status=(200,))


def test_rag_endpoint_reachable():
    payload = {"code": "", "query": "hello world"}
    _assert_json_response("/api/rag/query", method="POST", payload=payload, headers={"X-API-Key": "viewer-key"}, ok_status=(200, 400, 422))
