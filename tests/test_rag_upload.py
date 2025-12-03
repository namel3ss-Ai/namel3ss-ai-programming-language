from fastapi.testclient import TestClient

from namel3ss.server import create_app


def test_rag_upload_endpoint_indexes_text():
    client = TestClient(create_app())
    content = b"hello upload"
    files = {"file": ("note.txt", content, "text/plain")}
    res = client.post("/api/rag/upload", files=files, data={"index": "upload"}, headers={"X-API-Key": "dev-key"})
    assert res.status_code == 200
    assert res.json()["indexed"] == 1
