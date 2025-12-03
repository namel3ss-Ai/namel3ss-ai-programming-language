import asyncio
from datetime import datetime, timedelta, timezone

from namel3ss.agent.engine import AgentRunner
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.flows.triggers import FlowTrigger, TriggerManager
from namel3ss.ir import IRAgent, IRModel, IRProgram
from namel3ss.memory.engine import MemoryEngine
from namel3ss.memory.models import MemorySpaceConfig, MemoryType
from namel3ss.runtime.context import ExecutionContext
from namel3ss.tools.registry import ToolRegistry
from namel3ss.distributed.queue import JobQueue


def test_schedule_trigger_enqueues_job():
    queue = JobQueue()
    tm = TriggerManager(queue)
    trigger = FlowTrigger(id="t1", kind="schedule", flow_name="flow_a", config={"interval_seconds": 1})
    asyncio.run(tm.a_register_trigger(trigger))
    fired = asyncio.run(tm.a_tick_schedules(now=datetime.now(timezone.utc) + timedelta(seconds=2)))
    assert len(fired) == 1
    assert queue.list()[0].target == "flow_a"


def test_http_trigger_fires_immediately():
    queue = JobQueue()
    tm = TriggerManager(queue)
    trigger = FlowTrigger(id="http1", kind="http", flow_name="flow_http", config={})
    asyncio.run(tm.a_register_trigger(trigger))
    job = asyncio.run(tm.a_fire_trigger("http1", {"payload": True}))
    assert job is not None
    assert queue.list()[0].payload["trigger_id"] == "http1"


def test_memory_trigger_invoked_on_write():
    queue = JobQueue()
    tm = TriggerManager(queue)
    trigger = FlowTrigger(id="mem", kind="memory", flow_name="flow_mem", config={"space": "alpha"})
    tm.register_trigger(trigger)
    spaces = [MemorySpaceConfig(name="alpha", type=MemoryType.CONVERSATION)]
    memory = MemoryEngine(spaces, trigger_manager=tm)
    memory.add_item("alpha", "hello", MemoryType.CONVERSATION)
    assert queue.list()[0].target == "flow_mem"


def test_agent_signal_trigger():
    queue = JobQueue()
    tm = TriggerManager(queue)
    trigger = FlowTrigger(id="agent", kind="agent-signal", flow_name="followup", config={"agent": "helper"})
    tm.register_trigger(trigger)
    program = IRProgram(agents={"helper": IRAgent(name="helper")}, models={"default": IRModel(name="default")})
    registry = ModelRegistry()
    registry.register_model("default", provider_name=None)
    tools = ToolRegistry()
    agent_runner = AgentRunner(program, registry, tools, ModelRouter(registry))
    ctx = ExecutionContext(app_name="agent", request_id="req", trigger_manager=tm)
    agent_runner.run("helper", ctx)
    assert queue.list()[0].target == "followup"
