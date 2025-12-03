from fastapi.testclient import TestClient

from namel3ss.server import create_app
from namel3ss.distributed.queue import global_job_queue
from namel3ss.distributed.models import Job
from namel3ss.runtime.persistence.in_memory import InMemoryJobStore


def test_api_jobs_lists_queue():
    global_job_queue.store = InMemoryJobStore()
    client = TestClient(create_app())
    global_job_queue.enqueue(Job(id="job-1", type="flow", target="x"))
    resp = client.get("/api/jobs", headers={"X-API-Key": "dev-key"})
    assert resp.status_code == 200
    data = resp.json()
    assert "jobs" in data
    assert any(job["id"] == "job-1" for job in data["jobs"])
