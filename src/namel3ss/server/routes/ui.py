"""UI-related API routes (pages, manifests, flow execute/stream, events)."""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import asdict
from typing import Any, Callable, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from ..deps import Principal, Role, can_run_flow, can_view_pages, get_principal
from ..schemas import (
    PagesRequest,
    PageUIRequest,
    UIEventRequest,
    UIFlowExecuteRequest,
    UIManifestRequest,
)
from ...ui.runtime import UIEventRouter
from ...ui.components import UIEvent, UIContext
from ...obs.tracer import Tracer


def build_ui_router(
    parse_source_to_ir: Callable[[str], Any],
    project_ui_manifest: Callable[[], Dict[str, Any]],
    project_program: Callable[[], Any],
    engine_from_source: Callable[[str], Any],
    register_state_subscriber: Callable[[], asyncio.Queue],
    unregister_state_subscriber: Callable[[asyncio.Queue], None],
    broadcast_state_event: Callable[[dict[str, Any]], Any],
    serialize_stream_event: Callable[[Any], dict[str, Any]],
    global_state_stream_callback: Callable[[Any], Any],
    metrics_tracker,
    trigger_manager,
    plugin_registry,
    ExecutionContextCls,
) -> APIRouter:
    """Build the UI router."""

    router = APIRouter()

    @router.post("/api/pages")
    def api_pages(payload: PagesRequest, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if not can_view_pages(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        try:
            program = parse_source_to_ir(payload.code)
            pages = [{"name": page.name, "route": page.route, "title": page.title} for page in program.pages.values()]
            return {"pages": pages}
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/api/page-ui")
    def api_page_ui(payload: PageUIRequest, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if not can_view_pages(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        try:
            engine = engine_from_source(payload.code)
            if payload.page not in engine.program.pages:
                raise HTTPException(status_code=404, detail="Page not found")
            ui_page = engine.ui_renderer.from_ir_page(engine.program.pages[payload.page])
            runtime_components = engine.ui_renderer.build_runtime_components(engine.program.pages[payload.page])
            return {"ui": ui_page.__dict__, "components": [c.__dict__ for c in runtime_components]}
        except HTTPException:
            raise
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/api/ui/manifest")
    def api_ui_manifest_current(principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if not can_view_pages(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        try:
            return project_ui_manifest()
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/api/ui/flow/info")
    def api_ui_flow_info(name: str, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if not can_view_pages(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        try:
            program = project_program()
            if name not in program.flows:
                raise HTTPException(status_code=404, detail="Flow not found")
            return {"name": name, "args": {}, "returns": "any"}
        except HTTPException as exc:
            if exc.status_code == 400:
                raise HTTPException(status_code=404, detail=exc.detail)
            raise
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/api/ui/manifest")
    def api_ui_manifest(payload: UIManifestRequest, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if not can_view_pages(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        try:
            engine = engine_from_source(payload.code)
            manifest = engine.ui_renderer.build_ui_manifest(engine.program)
            return manifest
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/api/ui/state/stream")
    async def api_ui_state_stream(principal: Principal = Depends(get_principal)):
        if not can_view_pages(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        queue = register_state_subscriber()

        async def event_stream():
            try:
                while True:
                    item = await queue.get()
                    yield json.dumps(item) + "\n"
            finally:
                unregister_state_subscriber(queue)

        return StreamingResponse(event_stream(), media_type="application/json")  # type: ignore[name-defined]

    @router.post("/api/ui/flow/execute")
    def api_ui_flow_execute(payload: UIFlowExecuteRequest, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if not can_run_flow(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        try:
            if payload.source:
                engine = engine_from_source(payload.source)
            else:
                program = project_program()
                engine = engine_from_source(program.source_text if hasattr(program, "source_text") else "")  # type: ignore[attr-defined]
                engine.program = program
            engine.flow_engine.global_stream_callback = global_state_stream_callback
            result = engine.execute_flow(payload.flow, principal_role=principal.role.value, payload={"state": payload.args})
            return {"success": True, "result": result}
        except Exception as exc:  # pragma: no cover
            return {"success": False, "error": str(exc)}

    @router.post("/api/ui/flow/stream")
    async def api_ui_flow_stream(payload: UIFlowExecuteRequest, principal: Principal = Depends(get_principal)):
        if not can_run_flow(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        try:
            if payload.source:
                engine = engine_from_source(payload.source)
            else:
                program = project_program()
                engine = engine_from_source(program.source_text if hasattr(program, "source_text") else "")  # type: ignore[attr-defined]
                engine.program = program
            engine.flow_engine.global_stream_callback = global_state_stream_callback
            if payload.flow not in engine.program.flows:
                raise HTTPException(status_code=404, detail="Flow not found")
            flow = engine.program.flows[payload.flow]
            context = ExecutionContextCls(
                app_name="__flow__",
                request_id=str(uuid.uuid4()),
                memory_engine=engine.memory_engine,
                memory_stores=engine.memory_stores,
                rag_engine=engine.rag_engine,
                tracer=Tracer(),
                tool_registry=engine.tool_registry,
                metrics=metrics_tracker,
                secrets=engine.secrets_manager,
                trigger_manager=engine.trigger_manager,
            )
            initial_state = payload.args or {}

            queue: asyncio.Queue = asyncio.Queue()

            async def emit(event: Any):
                serialized = serialize_stream_event(event)
                await queue.put(serialized)
                await broadcast_state_event(serialized)

            async def runner():
                try:
                    result = await engine.flow_engine.run_flow_async(
                        flow, context, initial_state=initial_state, stream_callback=emit
                    )
                    if result.errors:
                        err = result.errors[0]
                        await emit(
                            {
                                "kind": "error",
                                "flow": flow.name,
                                "step": err.node_id or err.error,
                                "error": err.error,
                            }
                        )
                    else:
                        serialized_result = result.to_dict() if hasattr(result, "to_dict") else asdict(result)
                        await emit(
                            {
                                "kind": "flow_done",
                                "flow": flow.name,
                                "step": flow.steps[-1].name if flow.steps else flow.name,
                                "success": True,
                                "result": serialized_result,
                            }
                        )
                except Exception as exc:  # pragma: no cover
                    await emit({"kind": "error", "flow": flow.name, "step": flow.name, "error": str(exc)})
                finally:
                    await queue.put(None)

            asyncio.create_task(runner())

            async def event_stream():
                while True:
                    item = await queue.get()
                    if item is None:
                        break
                    yield json.dumps(item) + "\n"

            return StreamingResponse(event_stream(), media_type="application/json")  # type: ignore[name-defined]
        except HTTPException:
            raise
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/api/ui/event")
    async def api_ui_event(payload: UIEventRequest, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if not can_view_pages(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        try:
            engine = engine_from_source(payload.code)
            if payload.page not in engine.program.pages:
                raise HTTPException(status_code=404, detail="Page not found")
            router = UIEventRouter(
                flow_engine=engine.flow_engine,
                agent_runner=engine.agent_runner,
                tool_registry=engine.tool_registry,
                rag_engine=engine.rag_engine,
                job_queue=engine.job_queue,
                memory_engine=engine.memory_engine,
                tracer=metrics_tracker and Tracer(),
                metrics=metrics_tracker,
            )
            components = engine.ui_renderer.build_runtime_components(engine.program.pages[payload.page])
            target_comp = next((c for c in components if c.id == payload.component_id), None)
            if not target_comp:
                raise HTTPException(status_code=404, detail="Component not found")
            ui_context = UIContext(
                app_name=engine.program.apps[list(engine.program.apps.keys())[0]].name if engine.program.apps else "__app__",
                page_name=payload.page,
                metadata={"execution_context": engine._build_default_execution_context()},
            )
            event = UIEvent(component_id=payload.component_id, event=payload.event, payload=payload.payload)
            result = await router.a_handle_event(target_comp, event, ui_context)
            return {"result": result.__dict__}
        except HTTPException:
            raise
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return router


__all__ = ["build_ui_router"]
