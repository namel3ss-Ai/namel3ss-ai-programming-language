import asyncio

from namel3ss.distributed.queue import JobQueue
from namel3ss.distributed.models import Job
from namel3ss.distributed.scheduler import JobScheduler
from namel3ss.distributed.workers import Worker


def test_job_queue_enqueue_dequeue():
    queue = JobQueue()
    job = queue.create_and_enqueue("flow", "pipeline", {})
    assert queue.get(job.id) is not None
    popped = queue.dequeue()
    assert popped.id == job.id


def test_worker_run_once_processes_job():
    queue = JobQueue()
    job = queue.create_and_enqueue("tool", "noop", {})

    class DummyRuntime:
        class DummyTools:
            def __init__(self):
                class DummyTool:
                    name = "noop"

                    def run(self, **kwargs):
                        return "ok"

                self.tool = DummyTool()

            def get(self, name):
                if name == "noop":
                    return self.tool
                return None

        def __init__(self):
            self.tool_registry = self.DummyTools()

        def execute_flow(self, name):
            return {"flow": name}

        def execute_agent(self, name):
            return {"agent": name}

        def execute_page_public(self, name):
            return {"page": name}

    worker = Worker(lambda code: DummyRuntime(), queue, None)
    asyncio.run(worker.run_once())
    assert job.status in ("success", "error")
