import asyncio
from pathlib import Path

import pytest

from namel3ss.distributed.file_watcher import FileWatcher
from namel3ss.distributed.queue import JobQueue
from namel3ss.flows.triggers import FlowTrigger, TriggerManager


def test_register_file_trigger_invalid_path(tmp_path: Path):
    mgr = TriggerManager(JobQueue(), project_root=tmp_path)
    trig = FlowTrigger(id="t1", kind="file", flow_name="flow", config={"path": str(tmp_path / "missing")})
    with pytest.raises(ValueError):
        mgr.register_trigger(trig)


def test_file_trigger_enqueue_payload(tmp_path: Path):
    mgr = TriggerManager(JobQueue(), project_root=tmp_path)
    trig = FlowTrigger(
        id="t1",
        kind="file",
        flow_name="flow",
        config={"path": str(tmp_path), "pattern": "*.txt", "include_content": True},
    )
    mgr.register_trigger(trig)
    f = tmp_path / "hello.txt"
    f.write_text("hello", encoding="utf-8")
    mgr.notify_file_event(f, "created")
    jobs = mgr.job_queue.list()
    assert len(jobs) == 1
    payload = jobs[0].payload
    assert payload["payload"]["event"] == "created"
    assert "hello.txt" in payload["payload"]["file"]
    assert payload["payload"]["content"] == "hello"


def test_disabled_file_trigger_no_job(tmp_path: Path):
    mgr = TriggerManager(JobQueue(), project_root=tmp_path)
    trig = FlowTrigger(
        id="t1", kind="file", flow_name="flow", config={"path": str(tmp_path)}, enabled=False, next_fire_at=None
    )
    mgr.register_trigger(trig)
    f = tmp_path / "file.txt"
    f.write_text("x")
    mgr.notify_file_event(f, "created")
    assert len(mgr.job_queue.list()) == 0


def test_file_watcher_poll_detects_change(tmp_path: Path):
    queue = JobQueue()
    mgr = TriggerManager(queue, project_root=tmp_path)
    watcher = FileWatcher(mgr, tmp_path, poll_interval=0.01)
    mgr.file_watcher = watcher
    trig = FlowTrigger(id="t1", kind="file", flow_name="flow", config={"path": str(tmp_path), "pattern": "*.txt"})
    mgr.register_trigger(trig)
    f = tmp_path / "watched.txt"
    f.write_text("data", encoding="utf-8")
    asyncio.run(watcher.poll_once())
    assert len(queue.list()) == 1
    payload = queue.list()[0].payload["payload"]
    assert payload["event"] == "created"
