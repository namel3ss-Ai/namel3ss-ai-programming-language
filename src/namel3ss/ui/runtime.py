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
from ..ir import IRProgram, IRPage
from ..ui.components import UIComponentInstance, UIContext, UIEvent, UIEventHandler, UIEventResult
from ..ui.validation import validate_form
import re
from ..runtime.expressions import ExpressionEvaluator, VariableEnvironment
from ..errors import Namel3ssError


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
            # Input/textarea validation (page-level) if manifest is available
            page_manifest = context.metadata.get("page_manifest") if context and context.metadata else None
            if page_manifest:
                payload_state = event.payload or {}
                valid, errors = validate_inputs(page_manifest, payload_state)
                if not valid:
                    return UIEventResult(success=False, validation_errors=errors, messages=["validation_failed"])
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


def _walk_layout(layout: list[dict], collector: list[dict]) -> None:
    for el in layout:
        if not isinstance(el, dict):
            continue
        if el.get("type") in {"input", "textarea"}:
            collector.append(el)
        # children keys
        for key in ("layout", "children"):
            if key in el and isinstance(el[key], list):
                _walk_layout(el[key], collector)


def validate_inputs(page_manifest: dict, state_payload: dict[str, Any]) -> tuple[bool, dict[str, str]]:
    errors: dict[str, str] = {}
    layout = page_manifest.get("layout") or []
    inputs: list[dict] = []
    _walk_layout(layout, inputs)
    state_data = state_payload.get("state") if isinstance(state_payload, dict) and "state" in state_payload else state_payload
    for el in inputs:
        validation = el.get("validation") or {}
        if not validation:
            continue
        binding = el.get("binding") or {}
        field = binding.get("path") or el.get("name") or el.get("label")
        if not field:
            continue
        value = None
        lookup_field = field
        if field.startswith("state."):
            lookup_field = field[len("state.") :]
        if isinstance(state_data, dict):
            value = state_data.get(field)
            if value is None:
                value = state_data.get(lookup_field)
        if validation.get("required") and (value is None or value == ""):
            errors[field] = validation.get("message") or "Value is required."
            continue
        if value is None:
            continue
        text_val = str(value)
        min_len = validation.get("minLength")
        max_len = validation.get("maxLength")
        if min_len is not None and len(text_val) < int(min_len):
            errors[field] = validation.get("message") or f"Minimum length is {min_len}."
            continue
        if max_len is not None and len(text_val) > int(max_len):
            errors[field] = validation.get("message") or f"Maximum length is {max_len}."
            continue
        pattern = validation.get("pattern")
        if pattern:
            try:
                normalized_pattern = pattern
                try:
                    normalized_pattern = pattern.encode("utf-8").decode("unicode_escape")
                except Exception:
                    normalized_pattern = pattern
                if not re.search(normalized_pattern, text_val):
                    errors[field] = validation.get("message") or "Value does not match pattern."
            except re.error:
                errors[field] = validation.get("message") or "Invalid pattern."
    return len(errors) == 0, errors

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


class UIStateStore:
    """Simple reactive state store for UI pages."""

    def __init__(self, initial: Optional[Dict[str, Any]] = None) -> None:
        self._state: Dict[str, Any] = dict(initial or {})
        self._subs: list = []

    def get(self, name: str) -> Any:
        return self._state.get(name)

    def set(self, name: str, value: Any) -> None:
        self._state[name] = value
        for sub in list(self._subs):
            try:
                sub(name, value)
            except Exception:
                continue

    def snapshot(self) -> Dict[str, Any]:
        return dict(self._state)

    def subscribe(self, callback) -> None:
        self._subs.append(callback)


def _eval_expr(expr, state: UIStateStore, extra_env: Optional[Dict[str, Any]] = None) -> Any:
    env = VariableEnvironment(backing={**(extra_env or {}), **state.snapshot()})

    def resolver(name: str):
        if name == "state":
            return True, state.snapshot()
        if env.has(name):
            return True, env.resolve(name)
        return False, None

    evaluator = ExpressionEvaluator(env, resolver=resolver, rulegroup_resolver=None, helper_resolver=None)
    return evaluator.evaluate(expr)


def render_layout(layout, state: UIStateStore, theme: Optional[Dict[str, Any]] = None, components=None, extra_env: Optional[Dict[str, Any]] = None):
    rendered = []
    theme = theme or {}
    components = components or {}
    for el in layout:
        from ..ir import (
            IRHeading,
            IRText,
            IRImage,
            IREmbedForm,
            IRSection,
            IRUIInput,
            IRUIButton,
            IRUIConditional,
            IRUIComponentCall,
            IRUIStyle,
            IRCard,
    IRRow,
    IRColumn,
    IRTextarea,
    IRBadge,
    IRMessageList,
    IRMessage,
)

        def apply_styles(styles):
            resolved = []
            for st in styles:
                if isinstance(st, IRUIStyle):
                    val = st.value
                    if st.kind in {"color", "background"} and isinstance(val, str) and val in theme:
                        val = theme[val]
                    resolved.append({"kind": st.kind, "value": val})
            return resolved

        if isinstance(el, IRHeading):
            rendered.append({"type": "heading", "text": el.text, "styles": apply_styles(getattr(el, "styles", []))})
            continue
        if isinstance(el, IRText):
            value = el.text
            if getattr(el, "expr", None) is not None:
                try:
                    evaluated = _eval_expr(el.expr, state, extra_env)
                    value = str(evaluated)
                except Exception:
                    value = el.text
            rendered.append({"type": "text", "text": value, "styles": apply_styles(getattr(el, "styles", []))})
            continue
        if isinstance(el, IRImage):
            rendered.append({"type": "image", "url": el.url, "styles": apply_styles(getattr(el, "styles", []))})
            continue
        if isinstance(el, IREmbedForm):
            rendered.append({"type": "form", "form_name": el.form_name, "styles": apply_styles(getattr(el, "styles", []))})
            continue
        if isinstance(el, IRUIInput):
            rendered.append(
                {
                    "type": "input",
                    "label": el.label,
                    "name": el.var_name,
                    "field_type": el.field_type,
                    "value": state.get(el.var_name),
                    "styles": apply_styles(getattr(el, "styles", [])),
                }
            )
            continue
        if isinstance(el, IRUIButton):
            label = el.label
            if getattr(el, "label_expr", None) is not None:
                try:
                    maybe = _eval_expr(el.label_expr, state, extra_env)
                    label = str(maybe)
                except Exception:
                    label = el.label
            rendered.append(
                {
                    "type": "button",
                    "label": label,
                    "actions": [{"kind": a.kind, "target": a.target, "args": a.args} for a in el.actions],
                    "styles": apply_styles(getattr(el, "styles", [])),
                }
            )
            continue
        if isinstance(el, IRUIConditional):
            cond_val = True
            if el.condition is not None:
                try:
                    cond_val = bool(_eval_expr(el.condition, state, extra_env))
                except Exception:
                    cond_val = False
            branch = el.when_block.layout if cond_val and el.when_block else el.otherwise_block.layout if el.otherwise_block else []
            rendered.extend(render_layout(branch, state, theme=theme, components=components, extra_env=extra_env))
            continue
        if isinstance(el, IRCard):
            rendered.append(
                {
                    "type": "card",
                    "title": el.title,
                    "layout": render_layout(el.layout, state, theme=theme, components=components, extra_env=extra_env),
                    "styles": apply_styles(getattr(el, "styles", [])),
                }
            )
            continue
        if isinstance(el, IRRow):
            rendered.append(
                {
                    "type": "row",
                    "layout": render_layout(el.layout, state, theme=theme, components=components, extra_env=extra_env),
                    "styles": apply_styles(getattr(el, "styles", [])),
                }
            )
            continue
        if isinstance(el, IRColumn):
            rendered.append(
                {
                    "type": "column",
                    "layout": render_layout(el.layout, state, theme=theme, components=components, extra_env=extra_env),
                    "styles": apply_styles(getattr(el, "styles", [])),
                }
            )
            continue
        if isinstance(el, IRTextarea):
            rendered.append(
                {
                    "type": "textarea",
                    "label": el.label,
                    "name": el.var_name or el.label,
                    "value": state.get(el.var_name or el.label),
                    "styles": apply_styles(getattr(el, "styles", [])),
                }
            )
            continue
        if isinstance(el, IRBadge):
            rendered.append(
                {
                    "type": "badge",
                    "text": el.text,
                    "styles": apply_styles(getattr(el, "styles", [])),
                }
            )
            continue
        if isinstance(el, IRMessageList):
            rendered.append(
                {
                    "type": "message_list",
                    "layout": render_layout(el.layout, state, theme=theme, components=components, extra_env=extra_env),
                    "styles": apply_styles(getattr(el, "styles", [])),
                }
            )
            continue
        if isinstance(el, IRMessage):
            role_val = None
            if el.role is not None:
                try:
                    role_val = _eval_expr(el.role, state, extra_env)
                except Exception:
                    role_val = None
            text_val = None
            if el.text_expr is not None:
                try:
                    text_val = _eval_expr(el.text_expr, state, extra_env)
                except Exception:
                    text_val = None
                if text_val is None and hasattr(el.text_expr, "target") and hasattr(el.text_expr, "field"):
                    target = getattr(el.text_expr, "target", None)
                    if getattr(target, "name", None) == "state":
                        snapshot = state.snapshot()
                        text_val = snapshot.get(getattr(el.text_expr, "field", ""))
            rendered.append(
                {
                    "type": "message",
                    "name": el.name,
                    "role": role_val,
                    "text": text_val,
                    "styles": apply_styles(getattr(el, "styles", [])),
                }
            )
            continue
        if isinstance(el, IRUIComponentCall):
            comp = components.get(el.name)
            if comp:
                env_map = dict(extra_env or {})
                for idx, arg in enumerate(el.args):
                    if idx < len(comp.params):
                        try:
                            env_map[comp.params[idx]] = _eval_expr(arg, state, extra_env)
                        except Exception:
                            env_map[comp.params[idx]] = None
                rendered.extend(
                    render_layout(
                        comp.render,
                        state,
                        theme=theme,
                        components=components,
                        extra_env=env_map,
                    )
                )
            else:
                rendered.append({"type": "component_call", "name": el.name, "styles": apply_styles(getattr(el, "styles", []))})
            continue
        if isinstance(el, IRSection):
            rendered.append({"type": "section", "name": el.name, "layout": render_layout(el.layout, state, theme=theme, components=components, extra_env=extra_env), "styles": apply_styles(getattr(el, "styles", []))})
            continue
    return rendered


class UIPresenter:
    """Minimal reactive runtime for UI-2."""

    def __init__(self, page_ir, components=None, theme=None) -> None:
        initial_state = {s.name: s.initial for s in getattr(page_ir, "ui_states", [])}
        self.state = UIStateStore(initial_state)
        self.page = page_ir
        self.components = components or {}
        self.theme = theme or {}
        self.rendered = render_layout(page_ir.layout, self.state, theme=self.theme, components=self.components)
        self.state.subscribe(lambda *_: self._rerender())

    def _rerender(self):
        self.rendered = render_layout(self.page.layout, self.state, theme=self.theme, components=self.components)

    def set_state(self, name: str, value: Any) -> None:
        self.state.set(name, value)

    def click(self, label: str, dispatcher=None):
        actions = []

        def walk(layout):
            from ..ir import IRUIButton, IRSection, IRUIConditional

            for node in layout:
                if isinstance(node, IRUIButton) and node.label == label:
                    actions.extend(node.actions)
                elif isinstance(node, IRSection):
                    walk(node.layout)
                elif isinstance(node, IRUIConditional):
                    cond_val = True
                    if node.condition is not None:
                        try:
                            cond_val = bool(_eval_expr(node.condition, self.state))
                        except Exception:
                            cond_val = False
                    branch = node.when_block.layout if cond_val and node.when_block else node.otherwise_block.layout if node.otherwise_block else []
                    walk(branch)

        walk(self.page.layout)
        for action in actions:
            if dispatcher:
                dispatcher(action, self.state.snapshot())
        return actions


class NavigationState:
    def __init__(self, current_path: str = "/", current_page_name: str | None = None):
        self.current_path = current_path
        self.current_page_name = current_page_name


class Router:
    def __init__(self, program: IRProgram, initial_path: str = "/") -> None:
        self.program = program
        self.state = NavigationState(current_path=initial_path, current_page_name=self._resolve_page_name(initial_path))

    def _resolve_page_name(self, path: str) -> str | None:
        for page in self.program.pages.values():
            if page.route == path:
                return page.name
        return None

    def navigate_to_path(self, path: str) -> None:
        self.state.current_path = path
        self.state.current_page_name = self._resolve_page_name(path)

    def navigate_to_page(self, page_name: str) -> None:
        page = self.program.pages.get(page_name)
        if not page:
            raise Namel3ssError(f"Page '{page_name}' not found")
        self.state.current_page_name = page.name
        self.state.current_path = page.route or f"/{page.name}"

    def get_current_page(self) -> IRPage | None:
        if self.state.current_page_name and self.state.current_page_name in self.program.pages:
            return self.program.pages[self.state.current_page_name]
        # fallback by path
        name = self._resolve_page_name(self.state.current_path)
        if name and name in self.program.pages:
            return self.program.pages[name]
        return None


def handle_ui_action(action, router: Router | None = None):
    if not router:
        return
    if action.kind == "navigate":
        if action.target_page:
            router.navigate_to_page(action.target_page)
        elif action.target_path:
            router.navigate_to_path(action.target_path)


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
