import asyncio

from namel3ss.ai.models import ModelStreamChunk
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import SelectedModel
from namel3ss.agent.engine import AgentRunner
from namel3ss.errors import Namel3ssError
from namel3ss.flows.engine import FlowEngine
from namel3ss.ir import IRAiCall, IRFlow, IRFlowStep, IRProgram
from namel3ss.runtime.context import ExecutionContext
from namel3ss.tools.registry import ToolRegistry


class FakeRouter:
    def __init__(self, chunks):
        self.chunks = chunks

    def select_model(self, logical_name=None):
        return SelectedModel(model_name="dummy", provider_name="dummy", actual_model="dummy")

    def stream(self, messages, model=None, tools=None, json_mode=False, **kwargs):
        return list(self.chunks)


async def _run_flow_with_router(router, raise_errors=False):
    registry = ModelRegistry()
    registry.register_model("dummy", None)
    program = IRProgram(
        ai_calls={"bot": IRAiCall(name="bot", model_name="dummy", input_source="hi")},
        flows={
            "f": IRFlow(
                name="f",
                description=None,
                steps=[IRFlowStep(name="answer", kind="ai", target="bot", params={"streaming": True})],
                error_steps=[],
            )
        },
    )
    engine = FlowEngine(
        program=program,
        model_registry=registry,
        tool_registry=ToolRegistry(),
        agent_runner=AgentRunner(program=program, model_registry=registry, tool_registry=ToolRegistry(), router=router),
        router=router,
    )
    events = []

    async def emit(evt):
        events.append(evt)

    ctx = ExecutionContext(app_name="test", request_id="req-1")
    result = await engine.run_flow_async(program.flows["f"], ctx, stream_callback=emit)
    if raise_errors:
        return result, events
    assert result.state.get("last_output") == "Hello"
    # ai_chunk events should be emitted
    assert {"event": "ai_chunk", "step": "answer", "delta": "Hel"} in events
    assert {"event": "ai_chunk", "step": "answer", "delta": "lo"} in events
    assert {"event": "ai_done", "step": "answer", "full": "Hello"} in events


def test_flow_streaming_happy_path():
    chunks = [
        ModelStreamChunk(provider="dummy", model="dummy", delta="Hel", raw={}, is_final=False),
        ModelStreamChunk(provider="dummy", model="dummy", delta="lo", raw={}, is_final=True),
    ]
    router = FakeRouter(chunks)
    asyncio.run(_run_flow_with_router(router))


def test_flow_streaming_error_propagates():
    class ErrorRouter(FakeRouter):
        def stream(self, messages, model=None, tools=None, json_mode=False, **kwargs):
            raise Namel3ssError("boom")

    router = ErrorRouter([])
    registry = ModelRegistry()
    registry.register_model("dummy", None)
    program = IRProgram(
        ai_calls={"bot": IRAiCall(name="bot", model_name="dummy", input_source="hi")},
        flows={
            "f": IRFlow(
                name="f",
                description=None,
                steps=[IRFlowStep(name="answer", kind="ai", target="bot", params={"streaming": True})],
                error_steps=[],
            )
        },
    )
    engine = FlowEngine(
        program=program,
        model_registry=registry,
        tool_registry=ToolRegistry(),
        agent_runner=AgentRunner(program=program, model_registry=registry, tool_registry=ToolRegistry(), router=router),
        router=router,
    )
    events = []

    async def emit(evt):
        events.append(evt)

    ctx = ExecutionContext(app_name="test", request_id="req-err")
    result = asyncio.run(engine.run_flow_async(program.flows["f"], ctx, stream_callback=emit))
    assert result.errors  # unhandled error recorded
    assert any(evt.get("event") == "flow_error" for evt in events)
