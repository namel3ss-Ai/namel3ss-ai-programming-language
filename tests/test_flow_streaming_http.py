import asyncio
import json

from fastapi.testclient import TestClient

from namel3ss.flows.engine import FlowEngine
from namel3ss.flows.models import FlowRunResult, StreamEvent
from namel3ss.server import create_app


async def _fake_run_flow_async(self, flow, context, initial_state=None, stream_callback=None):
    events: list[StreamEvent] = [
        {
            "kind": "chunk",
            "flow": flow.name,
            "step": "answer",
            "channel": "chat",
            "role": "assistant",
            "label": "Support Bot",
            "mode": "tokens",
            "delta": "Hel",
        },
        {
            "kind": "done",
            "flow": flow.name,
            "step": "answer",
            "channel": "chat",
            "role": "assistant",
            "label": "Support Bot",
            "mode": "tokens",
            "full": "Hel",
        },
    ]
    if stream_callback:
        for evt in events:
            await stream_callback(evt)
    return FlowRunResult(flow_name=flow.name)

async def _fake_run_flow_async_state(self, flow, context, initial_state=None, stream_callback=None):
    if stream_callback:
        await stream_callback(
            {
                "kind": "state_change",
                "flow": flow.name,
                "step": "inc",
                "path": "counter",
                "old_value": 1,
                "new_value": 2,
            }
        )
    return FlowRunResult(flow_name=flow.name)


def test_flow_stream_endpoint_serializes_stream_metadata(monkeypatch):
    monkeypatch.setattr(FlowEngine, "run_flow_async", _fake_run_flow_async)
    app = create_app()
    client = TestClient(app)
    source = """
flow is "chat_turn":
  step is "answer":
    kind is "ai"
    target is "bot"
    streaming is true

ai is "bot":
  model is "dummy"

model "dummy":
  provider "openai:gpt-4.1-mini"
"""
    response = client.post(
        "/api/ui/flow/stream",
        json={"flow": "chat_turn", "source": source, "args": {}},
        headers={"X-API-Key": "dev-key"},
    )
    assert response.status_code == 200
    lines = list(response.iter_lines())
    assert lines
    first_line = lines[0].decode() if isinstance(lines[0], (bytes, bytearray)) else lines[0]
    first = json.loads(first_line)
    assert first["event"] == "ai_chunk"
    assert first["flow"] == "chat_turn"
    assert first["channel"] == "chat"
    assert first["role"] == "assistant"
    assert first["label"] == "Support Bot"
    assert first["mode"] == "tokens"


def test_state_stream_endpoint_receives_events(monkeypatch):
    monkeypatch.setattr(FlowEngine, "run_flow_async", _fake_run_flow_async_state)
    app = create_app()
    queue = app.state.register_state_subscriber()
    asyncio.run(
        app.state.broadcast_state_event(
            {"event": "state_change", "flow": "counter", "step": "inc", "path": "counter", "new_value": 2, "old_value": 1}
        )
    )
    evt = asyncio.run(queue.get())
    assert evt["event"] == "state_change"
    assert evt["path"] == "counter"
