"""
Worker entrypoint for deployed environments.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from namel3ss.server import create_app
from namel3ss.runtime.engine import Engine
from namel3ss.distributed.workers import Worker
from namel3ss.distributed.queue import global_job_queue
from namel3ss.obs.tracer import Tracer


def _load_source() -> str:
    source_path = Path(os.getenv("N3_SOURCE_PATH", "app.ai"))
    if source_path.exists():
        return source_path.read_text(encoding="utf-8")
    return ""


def build_worker() -> Worker:
    code = _load_source()
    return Worker(
        runtime_factory=lambda _: Engine.from_source(code or "", trigger_manager=None),
        job_queue=global_job_queue,
        tracer=Tracer(),
    )


async def main() -> None:
    worker = build_worker()
    await worker.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
