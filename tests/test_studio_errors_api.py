import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastapi.testclient import TestClient

from namel3ss.observability.tracing import default_tracer
from namel3ss.server import create_app


def _client(tmp_path: Path) -> TestClient:
    prev = os.getcwd()
    os.chdir(tmp_path)
    try:
        return TestClient(create_app())
    finally:
        os.chdir(prev)


def test_studio_error_detail(tmp_path: Path):
    span = default_tracer.start_span("flow.error", attributes={"flow": "demo"})
    span.exception = "boom"
    default_tracer.finish_span(span)

    (tmp_path / "main.ai").write_text('flow is "noop":\n  step is "s":\n    log info "ok"\n', encoding="utf-8")
    client = _client(tmp_path)

    resp = client.get(f"/api/studio/errors/{span.context.span_id}", headers={"X-API-Key": "dev-key"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["message"] == "boom"
