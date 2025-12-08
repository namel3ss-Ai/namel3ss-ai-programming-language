import asyncio

from namel3ss.ai.models import ModelStreamChunk
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import SelectedModel
from namel3ss.agent.engine import AgentRunner
from namel3ss.errors import Namel3ssError
from namel3ss.flows.engine import FlowEngine
from namel3ss.flows.models import FlowRunResult, StreamEvent
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


async def _run_flow_with_router(
    router,
    stream_mode: str = "tokens",
    chunks: list | None = None,
) -> tuple[FlowRunResult, list[StreamEvent]]:
    registry = ModelRegistry()
    registry.register_model("dummy", None)
    program = IRProgram(
        ai_calls={"bot": IRAiCall(name="bot", model_name="dummy", input_source="hi")},
        flows={
            "f": IRFlow(
                name="f",
                description=None,
                steps=[
                    IRFlowStep(
                        name="answer",
                        kind="ai",
                        target="bot",
                        params={"streaming": True, "stream_channel": "chat", "stream_role": "assistant", "stream_label": "Bot", "stream_mode": stream_mode},
                        streaming=True,
                        stream_channel="chat",
                        stream_role="assistant",
                        stream_label="Bot",
                        stream_mode=stream_mode,
                    )
                ],
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
    events: list[StreamEvent] = []

    async def emit(evt: StreamEvent):
        events.append(evt)

    ctx = ExecutionContext(app_name="test", request_id="req-1")
    result = await engine.run_flow_async(program.flows["f"], ctx, stream_callback=emit)
    return result, events


def test_flow_streaming_tokens_mode():
    chunks = [
        ModelStreamChunk(provider="dummy", model="dummy", delta="Hel", raw={}, is_final=False),
        ModelStreamChunk(provider="dummy", model="dummy", delta="lo", raw={}, is_final=True),
    ]
    router = FakeRouter(chunks)
    result, events = asyncio.run(_run_flow_with_router(router, stream_mode="tokens"))
    assert result.state.get("last_output") == "Hello"
    assert any(evt["kind"] == "chunk" and evt["delta"] == "Hel" and evt["channel"] == "chat" for evt in events)
    assert any(evt["kind"] == "chunk" and evt["delta"] == "lo" for evt in events)
    done = [evt for evt in events if evt["kind"] == "done"]
    assert done and done[0]["full"] == "Hello"
    assert all(evt.get("mode") == "tokens" for evt in events)


def test_flow_streaming_full_mode_emits_single_done():
    chunks = [
        ModelStreamChunk(provider="dummy", model="dummy", delta="Hel", raw={}, is_final=False),
        ModelStreamChunk(provider="dummy", model="dummy", delta="lo", raw={}, is_final=True),
    ]
    router = FakeRouter(chunks)
    result, events = asyncio.run(_run_flow_with_router(router, stream_mode="full"))
    assert result.state.get("last_output") == "Hello"
    assert not any(evt["kind"] == "chunk" for evt in events)
    done = [evt for evt in events if evt["kind"] == "done"]
    assert done and done[0]["full"] == "Hello"
    assert all(evt.get("mode") == "full" for evt in events)


def test_flow_streaming_sentence_mode_chunks_sentences():
    chunks = [
        ModelStreamChunk(provider="dummy", model="dummy", delta="Hello world. This is", raw={}, is_final=False),
        ModelStreamChunk(provider="dummy", model="dummy", delta=" great!", raw={}, is_final=True),
    ]
    router = FakeRouter(chunks)
    result, events = asyncio.run(_run_flow_with_router(router, stream_mode="sentences"))
    assert result.state.get("last_output") == "Hello world. This is great!"
    chunks_out = [evt for evt in events if evt["kind"] == "chunk"]
    assert any("Hello world." in evt["delta"] for evt in chunks_out)
    assert any("This is great!" in evt["delta"] for evt in chunks_out)
    done = [evt for evt in events if evt["kind"] == "done"]
    assert done and done[0]["full"] == "Hello world. This is great!"
    assert all(evt.get("mode") == "sentences" for evt in events)


def test_flow_streaming_error_propagates():
    class ErrorRouter(FakeRouter):
        def stream(self, messages, model=None, tools=None, json_mode=False, **kwargs):
            raise Namel3ssError("boom")

    router = ErrorRouter([])
    result, events = asyncio.run(_run_flow_with_router(router))
    assert result.errors  # unhandled error recorded
    assert any(evt.get("kind") == "error" and evt.get("error") == "boom" for evt in events)
