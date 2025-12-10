import asyncio

from fastapi.testclient import TestClient

from namel3ss.server import create_app


FLOW_PROGRAM = (
    'flow is "pipeline":\n'
    '  step is "call":\n'
    '    kind is "ai"\n'
    '    target is "summarise_message"\n'
    'model is "default":\n'
    '  provider is "openai_default"\n'
    'ai is "summarise_message":\n'
    '  model is "default"\n'
)


def test_submit_and_process_job_flow():
    client = TestClient(create_app())
    res = client.post(
        "/api/job/flow",
        json={"source": FLOW_PROGRAM, "flow": "pipeline"},
        headers={"X-API-Key": "dev-key"},
    )
    assert res.status_code == 200
    job_id = res.json()["job_id"]
    run_once = client.post("/api/worker/run-once", headers={"X-API-Key": "dev-key"})
    assert run_once.status_code == 200
    status = client.get(f"/api/job/{job_id}", headers={"X-API-Key": "viewer-key"})
    assert status.status_code == 200
    assert status.json()["job"]["status"] in ("queued", "running", "success")
