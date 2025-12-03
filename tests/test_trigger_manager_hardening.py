import asyncio
from datetime import timedelta
import pytest

from namel3ss.flows.triggers import FlowTrigger, TriggerManager
from namel3ss.distributed.queue import JobQueue


def test_disabled_trigger_does_not_enqueue():
    manager = TriggerManager(job_queue=JobQueue())
    trigger = FlowTrigger(id="t1", kind="http", flow_name="flow", config={}, enabled=False)
    manager.register_trigger(trigger)
    job = manager.fire_trigger("t1", {})
    assert job is None


@pytest.mark.slow
def test_schedule_tick_is_idempotent_per_window():
    manager = TriggerManager(job_queue=JobQueue())
    trigger = FlowTrigger(id="sched", kind="schedule", flow_name="flow", config={"interval_seconds": 1}, enabled=True)
    manager.register_trigger(trigger)
    fired_first = manager.fire_trigger("sched") if trigger.enabled else None
    assert fired_first is not None
    # Tick immediately should not double fire if next_fire_at is in the future
    future = trigger.next_fire_at - timedelta(milliseconds=10)
    fired = asyncio.run(async_tick_once(manager, now=future))
    assert fired == []


async def async_tick_once(manager: TriggerManager, now=None):
    return await manager.a_tick_schedules(now=now)
