from __future__ import annotations

import argparse
import asyncio
import statistics
import time
from uuid import uuid4

from namel3ss.runtime.engine import Engine
from namel3ss.runtime.context import ExecutionContext
from namel3ss.obs.tracer import Tracer


async def _run_single(engine: Engine, flow_name: str, semaphore: asyncio.Semaphore, durations: list[float], errors: list[str]) -> None:
    async with semaphore:
        flow = engine.program.flows[flow_name]
        context = ExecutionContext(app_name="load_test", request_id=str(uuid4()), tracer=Tracer())
        start = time.monotonic()
        try:
            await engine.flow_engine.run_flow_async(flow, context)
            durations.append(time.monotonic() - start)
        except Exception as exc:  # pragma: no cover - diagnostic helper
            errors.append(str(exc))


async def run_load_test(engine: Engine, flow_name: str, concurrency: int, total_requests: int) -> dict[str, float]:
    durations: list[float] = []
    errors: list[str] = []
    semaphore = asyncio.Semaphore(concurrency)
    tasks = [
        asyncio.create_task(_run_single(engine, flow_name, semaphore, durations, errors))
        for _ in range(total_requests)
    ]
    await asyncio.gather(*tasks)
    durations_sorted = sorted(durations)
    p95 = durations_sorted[int(0.95 * len(durations_sorted))] if durations_sorted else 0.0
    return {
        "total": total_requests,
        "errors": len(errors),
        "avg_latency_seconds": statistics.mean(durations) if durations else 0.0,
        "p95_latency_seconds": p95,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Simple flow load tester.")
    parser.add_argument("--program", required=True, help="Path to .n3 program file")
    parser.add_argument("--flow", required=True, help="Flow name to execute")
    parser.add_argument("--concurrency", type=int, default=4, help="Number of concurrent executions")
    parser.add_argument("--requests", type=int, default=20, help="Total number of flow runs")
    args = parser.parse_args()

    engine = Engine.from_file(args.program)
    summary = asyncio.run(run_load_test(engine, args.flow, args.concurrency, args.requests))
    print("Load test summary:")
    for key, value in summary.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()

