"""
UI runtime for handling component events and bindings.
"""

from __future__ import annotations

from dataclasses import asdict
import json
from typing import Any, Dict, Optional

from ..agent.engine import AgentRunner
from ..flows.engine import FlowEngine
from ..tools.registry import ToolRegistry
from ..metrics.tracker import MetricsTracker
from ..obs.tracer import Tracer
from ..memory.engine import MemoryEngine
from ..distributed.queue import JobQueue
from ..rag.engine import RAGEngine
from ..ui.components import UIComponentInstance, UIContext, UIEvent, UIEventHandler, UIEventResult
from ..ui.validation import validate_form


class UIEventRouter:
    def __init__(
        self,
        flow_engine: FlowEngine,
        agent_runner: AgentRunner,
        tool_registry: ToolRegistry,
        rag_engine: Optional[RAGEngine],
        job_queue: Optional[JobQueue],
        memory_engine: Optional[MemoryEngine],
        tracer: Optional[Tracer],
        metrics: Optional[MetricsTracker],
    ) -> None:
        self.flow_engine = flow_engine
        self.agent_runner = agent_runner
        self.tool_registry = tool_registry
        self.rag_engine = rag_engine
        self.job_queue = job_queue
        self.memory_engine = memory_engine
        self.tracer = tracer
        self.metrics = metrics

    async def a_handle_event(
        self,
        component: UIComponentInstance,
        event: UIEvent,
        context: UIContext,
    ) -> UIEventResult:
        matching = [h for h in component.events if h.event == event.event]
        if not matching:
            return UIEventResult(success=False, messages=["no handler"])

        handler = matching[0]
        # Form validation path
        if component.kind == "form":
            fields = component.props.get("fields", [])
            valid, errors = validate_form(fields, event.payload or {})
            if not valid:
                return UIEventResult(success=False, validation_errors=errors, messages=["validation_failed"])

        if handler.handler_kind == "flow":
            flow = self.flow_engine.program.flows.get(handler.target)
            if not flow:
                return UIEventResult(success=False, messages=["flow_not_found"])
            result = await self.flow_engine.run_flow_async(
                flow,
                context=context.metadata.get("execution_context"),  # may be None, FlowEngine will build new one
                initial_state={"ui_event": event.payload},
            )
            flow_payload = result.to_dict() if hasattr(result, "to_dict") else asdict(result)
            return UIEventResult(success=True, updated_state={"flow": flow_payload})

        if handler.handler_kind == "agent":
            if handler.target not in self.agent_runner.program.agents:
                return UIEventResult(success=False, messages=["agent_not_found"])
            exec_context = context.metadata.get("execution_context")
            agent_result = self.agent_runner.run(handler.target, exec_context)
            return UIEventResult(success=True, updated_state={"agent": asdict(agent_result)})

        if handler.handler_kind == "tool":
            tool = self.tool_registry.get(handler.target)
            if not tool:
                return UIEventResult(success=False, messages=["tool_not_found"])
            output = tool.run(**(event.payload or {}))
            if self.metrics:
                self.metrics.record_tool_call(provider=handler.target, cost=0.0005)
            return UIEventResult(success=True, updated_state={"tool": output})

        return UIEventResult(success=False, messages=["unsupported_handler"])

    def resolve_binding(self, component: UIComponentInstance) -> Dict[str, Any]:
        bindings = component.bindings or {}
        source = bindings.get("source")
        if not source:
            return {}
        if source == "jobs" and self.job_queue:
            return {"rows": [job.__dict__ for job in self.job_queue.list()]}
        if source == "memory" and self.memory_engine:
            space = bindings.get("space")
            items = self.memory_engine.list_all(space)
            return {"rows": [item.__dict__ for item in items]}
        if source == "rag" and self.rag_engine:
            query = bindings.get("query") or ""
            index = bindings.get("index")
            results = self.rag_engine.retrieve(index, query, top_k=bindings.get("k", 5))
            return {
                "rows": [
                    {"text": r.item.text, "score": r.score, "source": r.source, "metadata": r.item.metadata}
                    for r in results
                ]
            }
        if source == "metrics" and self.metrics:
            snap = self.metrics.snapshot()
            series = []
            flow_metrics = snap.get("flow_metrics", {})
            for key, value in flow_metrics.items():
                series.append({"label": key, "value": value})
            return {"series": series, "raw": snap}
        return {}


def map_component(comp_id: str, comp_type: str, props: dict, section: str, page: str) -> UIComponentInstance:
    kind = comp_type
    events = []
    bindings = {}
    parsed_props = dict(props)
    # If props contain json strings for structured fields, decode them.
    if "fields" in parsed_props and isinstance(parsed_props["fields"], str):
        try:
            parsed_props["fields"] = json.loads(parsed_props["fields"])
        except json.JSONDecodeError:
            parsed_props["fields"] = []
    if "fields" not in parsed_props:
        if "field" in parsed_props:
            required_flag = str(parsed_props.get("required", "")).lower() in {"true", "1", "yes"}
            parsed_props["fields"] = [{"id": parsed_props["field"], "required": required_flag}]
    if "value" in parsed_props and isinstance(parsed_props["value"], str):
        try:
            maybe = json.loads(parsed_props["value"])
            if isinstance(maybe, list):
                parsed_props["fields"] = maybe
            elif isinstance(maybe, dict) and "fields" in maybe:
                parsed_props["fields"] = maybe.get("fields", [])
                parsed_props["binding"] = maybe.get("binding", bindings)
                if "events" in maybe:
                    parsed_props["events"] = maybe["events"]
        except json.JSONDecodeError:
            if "fields" not in parsed_props:
                raw = parsed_props["value"]
                required_flag = "required" in raw or raw.endswith("!")
                field_id = raw.replace("!", "").split(":")[0]
                parsed_props["fields"] = [{"id": field_id, "required": required_flag}]
    if "binding" in parsed_props and isinstance(parsed_props.get("binding"), str):
        try:
            bindings = json.loads(parsed_props["binding"])
        except json.JSONDecodeError:
            bindings = {}
    # Simple conventions: props may carry event targets.
    if comp_type == "form":
        target_flow = props.get("on_submit_flow") or props.get("target")
        if target_flow:
            events.append(
                UIEventHandler(
                    event="submit",
                    handler_kind="flow",
                    target=target_flow,
                    config={},
                )
            )
    if "binding" in props:
        bindings = props.get("binding", {})
    return UIComponentInstance(
        id=comp_id,
        kind=kind,
        props=parsed_props,
        bindings=bindings,
        events=events,
    )
