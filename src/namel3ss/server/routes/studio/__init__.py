"""Studio-related API routes (inspection, flows, rag, ask)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Dict

from fastapi import APIRouter

from .base import register_base_routes
from .files import register_file_routes
from .macros import register_macro_routes
from .rag import register_rag_routes
from .traces import register_trace_routes


def build_studio_router(
    log_event,
    log_buffer,
    studio_status_payload: Callable[[], Dict[str, Any]],
    get_cached_program: Callable[[], Any],
    project_program: Callable[[], Any],
    build_project_engine: Callable[[Any], Any],
    parse_source_to_ir: Callable[[str], Any],
    project_ui_manifest_fn: Callable[[], Dict[str, Any]],
    build_canvas_manifest_fn: Callable[[Any], Dict[str, Any]],
    describe_memory_plan_fn,
    describe_memory_state_fn,
    ask_studio_fn,
    describe_ai_call_context_fn,
    inspect_entity_fn,
    studio_list_flows_fn,
    run_flow_once_fn,
    studio_list_rag_pipelines_fn,
    studio_describe_rag_pipeline_fn,
    collect_warnings_fn,
    invalidate_program_cache: Callable[[], None],
    set_cached_program: Callable[[Any], None],
    daemon_state,
    StudioDaemon_cls,
    project_root: Callable[[], Path],
    ignored_dirs: set[str],
    metrics_tracker,
    job_queue,
    trigger_manager,
    plugin_registry,
) -> APIRouter:
    """
    Build the Studio router. All heavy lifting is delegated to service helpers to
    preserve behavior while keeping handlers thin.
    """

    def _get_program(force_project: bool = False):
        return project_program() if force_project else get_cached_program()

    def _iter_ai_files(base: Path) -> list[Path]:
        files: list[Path] = []
        for root, dirs, file_names in os.walk(base):
            dirs[:] = [d for d in dirs if d not in ignored_dirs]
            for fname in sorted(file_names):
                if not fname.endswith(".ai"):
                    continue
                files.append(Path(root) / fname)
        return files

    router = APIRouter()

    register_base_routes(
        router,
        log_event=log_event,
        log_buffer=log_buffer,
        studio_status_payload=studio_status_payload,
        get_program=_get_program,
        project_program=project_program,
        build_project_engine=build_project_engine,
        parse_source_to_ir=parse_source_to_ir,
        build_canvas_manifest_fn=build_canvas_manifest_fn,
        describe_memory_plan_fn=describe_memory_plan_fn,
        describe_memory_state_fn=describe_memory_state_fn,
        ask_studio_fn=ask_studio_fn,
        describe_ai_call_context_fn=describe_ai_call_context_fn,
        inspect_entity_fn=inspect_entity_fn,
        studio_list_flows_fn=studio_list_flows_fn,
        run_flow_once_fn=run_flow_once_fn,
        collect_warnings_fn=collect_warnings_fn,
        invalidate_program_cache=invalidate_program_cache,
        set_cached_program=set_cached_program,
        daemon_state=daemon_state,
        StudioDaemon_cls=StudioDaemon_cls,
        job_queue=job_queue,
        trigger_manager=trigger_manager,
        plugin_registry=plugin_registry,
        metrics_tracker=metrics_tracker,
    )

    register_file_routes(
        router,
        project_root=project_root,
        project_ui_manifest_fn=project_ui_manifest_fn,
        iter_ai_files_fn=_iter_ai_files,
        ignored_dirs=ignored_dirs,
        invalidate_program_cache=invalidate_program_cache,
    )

    register_rag_routes(
        router,
        build_project_engine=build_project_engine,
        studio_list_rag_pipelines_fn=studio_list_rag_pipelines_fn,
        studio_describe_rag_pipeline_fn=studio_describe_rag_pipeline_fn,
        metrics_tracker=metrics_tracker,
        trigger_manager=trigger_manager,
        plugin_registry=plugin_registry,
    )

    register_macro_routes(router, project_root=project_root, iter_ai_files_fn=_iter_ai_files)

    register_trace_routes(router)

    return router


__all__ = ["build_studio_router"]
