"""Router composition for the FastAPI app."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

from fastapi import FastAPI

from ...distributed.queue import global_job_queue
from ...distributed.scheduler import JobScheduler
from ...distributed.workers import Worker
from ...lang.formatter import format_source
from ...migration.naming import migrate_source_to_naming_standard
from ...packaging.bundler import Bundler, make_server_bundle, make_worker_bundle
from ...ai.registry import ModelRegistry
from ...config import ProvidersConfig, load_config
from ...diagnostics.runner import collect_diagnostics, collect_lint, iter_ai_files
from ... import linting, ir
from ...flows.triggers import FlowTrigger
from ...optimizer.apply import SuggestionApplier
from ...optimizer.engine import OptimizerEngine
from ...optimizer.storage import OptimizerStorage
from ...optimizer.overlays import OverlayStore
from ...obs.tracer import Tracer
from ...runtime.context import clear_recall_snapshot
from ...runtime.engine import Engine
from ...secrets.manager import get_default_secrets_manager
from ...examples.manager import resolve_example_path, get_examples_root
from .policies import (
    compute_scope_keys,
    legacy_session_payload,
    long_term_key,
    long_term_store_name,
    profile_key,
    profile_store_name,
    short_term_store_name,
)
from .project import parse_source_to_ast, serialize_stream_event
from ..routes.health import build_health_router
from ..routes.compile import build_compile_router
from ..routes.run import build_run_router
from ..routes.studio import build_studio_router
from ..routes.plugins import build_plugins_router
from ..routes.triggers import build_triggers_router
from ..routes.jobs import build_jobs_router
from ..routes.optimizer import build_optimizer_router
from ..routes.rag import build_rag_router
from ..routes.memory import build_memory_router
from ..routes.ui import build_ui_router
from ..routes.diagnostics import build_diagnostics_router
from ..routes.metrics import build_metrics_router

if TYPE_CHECKING:
    from .factory import RoutingDeps


def include_routers(app: FastAPI, deps: RoutingDeps) -> None:
    """Include all routers in the correct order."""

    health_router = build_health_router(
        log_buffer=deps.log_buffer,
        log_event=deps.log_event,
        studio_status_payload=deps.studio_status_payload,
        project_root=deps.project_root,
        studio_static_dir=deps.studio_static_dir,
        studio_config_files=deps.studio_config_files,
    )
    app.include_router(health_router)

    studio_router = build_studio_router(
        log_event=deps.log_event,
        log_buffer=deps.log_buffer,
        studio_status_payload=deps.studio_status_payload,
        get_cached_program=deps.get_cached_program,
        project_program=deps.project_program,
        build_project_engine=deps.build_project_engine,
        parse_source_to_ir=deps.parse_source_to_ir,
        project_ui_manifest_fn=deps.project_ui_manifest,
        build_canvas_manifest_fn=deps.build_canvas_manifest_fn,
        describe_memory_plan_fn=deps.describe_memory_plan_fn,
        describe_memory_state_fn=deps.describe_memory_state_fn,
        ask_studio_fn=deps.ask_studio_fn,
        describe_ai_call_context_fn=deps.describe_ai_call_context_fn,
        inspect_entity_fn=deps.inspect_entity_fn,
        studio_list_flows_fn=deps.studio_list_flows_fn,
        run_flow_once_fn=deps.run_flow_once_fn,
        studio_list_rag_pipelines_fn=deps.studio_list_rag_pipelines_fn,
        studio_describe_rag_pipeline_fn=deps.studio_describe_rag_pipeline_fn,
        collect_warnings_fn=deps.collect_warnings_fn,
        invalidate_program_cache=deps.invalidate_program_cache,
        set_cached_program=deps.set_cached_program,
        daemon_state=deps.daemon_state,
        StudioDaemon_cls=deps.StudioDaemon_cls,
        project_root=deps.project_root,
        ignored_dirs=deps.ignored_dirs,
        metrics_tracker=deps.metrics_tracker,
        job_queue=deps.job_queue,
        trigger_manager=deps.trigger_manager,
        plugin_registry=deps.plugin_registry,
    )
    app.include_router(studio_router)

    compile_router = build_compile_router(
        parse_source_to_ast=parse_source_to_ast,
        format_source_fn=format_source,
        migrate_source_to_naming_standard=migrate_source_to_naming_standard,
        naming_migration_summary_cls=deps.naming_migration_summary_cls,
    )
    app.include_router(compile_router)

    diagnostics_router = build_diagnostics_router(
        parse_source_to_ir=deps.parse_source_to_ir,
        collect_diagnostics_fn=collect_diagnostics,
        collect_lint_fn=collect_lint,
        iter_ai_files_fn=iter_ai_files,
        lint_config_loader=linting.LintConfig.load,
        bundler_factory=Bundler,
        make_server_bundle_fn=make_server_bundle,
        make_worker_bundle_fn=make_worker_bundle,
        load_config_fn=load_config,
        providers_config_cls=ProvidersConfig,
        model_registry_cls=ModelRegistry,
        project_root=deps.project_root,
        engine_factory=deps.build_plugin_engine,
    )
    app.include_router(diagnostics_router)

    run_router = build_run_router(
        engine_cls=Engine,
        metrics_tracker=deps.metrics_tracker,
        trigger_manager=deps.trigger_manager,
        plugin_registry=deps.plugin_registry,
        store_trace=deps.store_trace,
        store_agent_traces=deps.store_agent_traces,
        get_last_trace=deps.get_last_trace,
        set_last_trace=deps.set_last_trace,
        recent_traces=deps.recent_traces,
        recent_agent_traces=deps.recent_agent_traces,
        resolve_example_path=resolve_example_path,
        get_examples_root=get_examples_root,
    )
    app.include_router(run_router)

    triggers_router = build_triggers_router(trigger_manager=deps.trigger_manager, flow_trigger_cls=FlowTrigger)
    app.include_router(triggers_router)

    plugins_router = build_plugins_router(
        plugin_registry=deps.plugin_registry,
        engine_factory=deps.build_plugin_engine,
    )
    app.include_router(plugins_router)

    optimizer_router = build_optimizer_router(
        optimizer_storage=deps.optimizer_storage,
        overlay_store=deps.overlay_store,
        get_default_secrets_manager=get_default_secrets_manager,
        tracer_cls=Tracer,
        optimizer_engine_cls=OptimizerEngine,
        suggestion_applier_cls=SuggestionApplier,
        metrics_tracker=deps.metrics_tracker,
    )
    app.include_router(optimizer_router)

    memory_router = build_memory_router(
        project_program=deps.project_program,
        build_project_engine=deps.build_project_engine,
        describe_memory_plan_fn=deps.describe_memory_plan_fn,
        describe_memory_state_fn=deps.describe_memory_state_fn,
        short_term_store_name_fn=short_term_store_name,
        long_term_store_name_fn=long_term_store_name,
        profile_store_name_fn=profile_store_name,
        long_term_key_fn=long_term_key,
        profile_key_fn=profile_key,
        compute_scope_keys_fn=compute_scope_keys,
        legacy_session_payload_fn=legacy_session_payload,
        clear_recall_snapshot_fn=clear_recall_snapshot,
        ir_module=ir,
    )
    app.include_router(memory_router)

    rag_router = build_rag_router(engine_factory=deps.build_engine_from_source)
    app.include_router(rag_router)

    metrics_router = build_metrics_router(metrics_tracker=deps.metrics_tracker)
    app.include_router(metrics_router)

    ui_router = build_ui_router(
        parse_source_to_ir=deps.parse_source_to_ir,
        project_ui_manifest=deps.project_ui_manifest,
        project_program=deps.project_program,
        engine_from_source=deps.build_engine_from_source,
        register_state_subscriber=deps.register_state_subscriber,
        unregister_state_subscriber=deps.unregister_state_subscriber,
        broadcast_state_event=deps.broadcast_state_event,
        serialize_stream_event=serialize_stream_event,
        global_state_stream_callback=deps.global_state_stream_callback,
        metrics_tracker=deps.metrics_tracker,
        trigger_manager=deps.trigger_manager,
        plugin_registry=deps.plugin_registry,
        ExecutionContextCls=deps.ExecutionContextCls,
    )
    app.include_router(ui_router)

    scheduler = JobScheduler(global_job_queue)
    worker = Worker(
        runtime_factory=lambda code: Engine.from_source(
            code or "",
            metrics_tracker=deps.metrics_tracker,
            trigger_manager=deps.trigger_manager,
            plugin_registry=deps.plugin_registry,
        ),
        job_queue=global_job_queue,
        tracer=Tracer(),
    )

    jobs_router = build_jobs_router(scheduler=scheduler, worker=worker, job_queue=global_job_queue)
    app.include_router(jobs_router)


__all__ = ["include_routers"]
