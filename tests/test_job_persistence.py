from namel3ss.distributed.models import Job
from namel3ss.distributed.queue import JobQueue
from namel3ss.runtime.persistence.sqlite import SQLiteJobStore


def test_persistent_jobs_round_trip(tmp_path):
    db_path = tmp_path / "jobs.db"
    store = SQLiteJobStore(db_path)
    queue1 = JobQueue(store=store)
    job = queue1.create_and_enqueue("flow", "pipeline", {"code": "snippet"})

    queue2 = JobQueue(store=store)
    loaded = queue2.get(job.id)
    assert loaded is not None
    assert loaded.status == "queued"

    dequeued = queue2.dequeue()
    assert dequeued is not None
    assert dequeued.id == job.id
    dequeued.result = {"ok": True}
    dequeued.status = "success"
    queue2.update(dequeued)

    queue3 = JobQueue(store=store)
    final = queue3.get(job.id)
    assert final is not None
    assert final.status == "success"
    assert final.result == {"ok": True}


def test_in_memory_jobs_not_persistent():
    queue1 = JobQueue()
    job = queue1.create_and_enqueue("flow", "pipeline", {"code": "snippet"})
    queue2 = JobQueue()
    assert queue2.get(job.id) is None
