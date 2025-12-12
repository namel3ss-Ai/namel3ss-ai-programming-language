"""
Flow execution engine V3: graph-based runtime with branching, parallelism, and
error boundaries.
"""

from __future__ import annotations

import asyncio
import urllib.error
from typing import Any, Optional

from ...agent.engine import AgentRunner
from ...ai.registry import ModelRegistry
from ...ai.router import ModelRouter
from ...errors import ProviderTimeoutError
from ...metrics.tracker import MetricsTracker
from ...runtime.circuit_breaker import default_circuit_breaker
from ...runtime.retries import get_default_retry_config
from ...runtime.frames import FrameRegistry
from ...runtime.vectorstores import VectorStoreRegistry
from ...secrets.manager import SecretsManager
from ...tools.registry import ToolConfig, ToolRegistry
from ...rag.graph import GraphEngine
from ..adapters.providers import _call_ai_step as _provider_call_ai_step, _stream_ai_step as _provider_stream_ai_step
from ..adapters.tools import (
    _allow_retry_for_method as _tools_allow_retry_for_method,
    _apply_tool_auth as _tools_apply_tool_auth,
    _coerce_tool_timeout as _tools_coerce_tool_timeout,
    _compute_tool_retry_delay as _tools_compute_tool_retry_delay,
    _execute_local_function as _tools_execute_local_function,
    _execute_tool_call as _tools_execute_tool_call,
    _http_json_request as _tools_http_json_request,
    _resolve_local_function as _tools_resolve_local_function,
    _should_retry_exception as _tools_should_retry_exception,
    _sleep_tool_retry as _tools_sleep_tool_retry,
)
from ..control.retries import _sleep_backoff as _retries_sleep_backoff
from ..control.timeouts import (
    _execute_with_timing as _timeouts_execute_with_timing,
    _extract_duration as _timeouts_extract_duration,
)
from ..models import FlowRunResult
from ..phases.execute import a_run_flow as _phases_a_run_flow, execute as _phases_execute
from ..phases.finalize import finalize as _phases_finalize
from ..phases.prepare import prepare as _phases_prepare
from ..state.context import ExecutionContext
from ..state.runtime import FlowEngineRuntimeMixin
from ..steps.auth import FlowEngineAuthMixin
from ..steps.conditions import FlowEngineConditionMixin
from ..steps.core import FlowEngineCoreMixin
from ..steps.expressions import FlowEngineExpressionMixin
from ..steps.inline import FlowEngineInlineMixin
from ..steps.script import FlowEngineScriptMixin
from ..steps.inputs import FlowEngineInputMixin
from ..steps.rag import FlowEngineRagMixin
from ..steps.records import FlowEngineRecordHelpersMixin, FlowEngineRecordOperationsMixin
from ..steps.results import FlowEngineResultMixin
from ..steps.router import (
    _eval_expr as _steps_eval_expr,
    _eval_rulegroup as _steps_eval_rulegroup,
    _match_pattern as _steps_match_pattern,
    _run_condition_node as _steps_run_condition_node,
)
from ..steps.runner import _execute_node as _steps_execute_node
from ...ir import IRFlow, IRProgram


class FlowEngine(
    FlowEngineCoreMixin,
    FlowEngineRuntimeMixin,
    FlowEngineInlineMixin,
    FlowEngineScriptMixin,
    FlowEngineAuthMixin,
    FlowEngineConditionMixin,
    FlowEngineExpressionMixin,
    FlowEngineInputMixin,
    FlowEngineRecordHelpersMixin,
    FlowEngineRecordOperationsMixin,
    FlowEngineResultMixin,
    FlowEngineRagMixin,
):
    _call_ai_step = _provider_call_ai_step
    _stream_ai_step = _provider_stream_ai_step
    _http_json_request = _tools_http_json_request
    _coerce_tool_timeout = _tools_coerce_tool_timeout
    _allow_retry_for_method = _tools_allow_retry_for_method
    _should_retry_exception = _tools_should_retry_exception
    _compute_tool_retry_delay = _tools_compute_tool_retry_delay
    _sleep_tool_retry = _tools_sleep_tool_retry
    _apply_tool_auth = _tools_apply_tool_auth
    _resolve_local_function = _tools_resolve_local_function
    _execute_local_function = _tools_execute_local_function
    _execute_tool_call = _tools_execute_tool_call
    _execute_with_timing = _timeouts_execute_with_timing
    _extract_duration = _timeouts_extract_duration
    _sleep_backoff = _retries_sleep_backoff
    _execute_node = _steps_execute_node
    _run_condition_node = _steps_run_condition_node
    _eval_rulegroup = _steps_eval_rulegroup
    _eval_expr = _steps_eval_expr
    _match_pattern = _steps_match_pattern
    a_run_flow = _phases_a_run_flow

    def __init__(
        self,
        program: IRProgram,
        model_registry: ModelRegistry,
        tool_registry: ToolRegistry,
        agent_runner: AgentRunner,
        router: ModelRouter,
        metrics: Optional[MetricsTracker] = None,
        secrets: Optional[SecretsManager] = None,
        max_parallel_tasks: int | None = None,
        global_stream_callback: Any = None,
    ) -> None:
        self.program = program
        self.model_registry = model_registry
        self.tool_registry = tool_registry
        self.agent_runner = agent_runner
        self.router = router
        self.metrics = metrics
        self.secrets = secrets
        from ...runtime.config import get_max_parallel_tasks

        self.max_parallel_tasks = max_parallel_tasks if max_parallel_tasks is not None else get_max_parallel_tasks()
        self.global_stream_callback = global_stream_callback
        self.frame_registry = FrameRegistry(program.frames if program else {})
        self.vector_registry = VectorStoreRegistry(program, secrets=secrets) if program else None
        self.graph_engine = GraphEngine(program.graphs if program else {}, program.graph_summaries if program else {})
        self.retry_config = get_default_retry_config()
        self.retry_error_types = (
            ProviderTimeoutError,
            urllib.error.URLError,
            ConnectionError,
            TimeoutError,
        )
        self.circuit_breaker = default_circuit_breaker
        if program and getattr(program, "tools", None):
            for tool in program.tools.values():
                if tool.name not in self.tool_registry.tools:
                    self.tool_registry.register(
                        ToolConfig(
                            name=tool.name,
                            kind=tool.kind,
                            method=tool.method,
                            url_expr=getattr(tool, "url_expr", None),
                            url_template=getattr(tool, "url_template", None),
                            headers=getattr(tool, "headers", {}) or {},
                            query_params=getattr(tool, "query_params", {}) or {},
                            body_fields=getattr(tool, "body_fields", {}) or {},
                            body_template=getattr(tool, "body_template", None),
                            input_fields=list(getattr(tool, "input_fields", []) or []),
                            timeout_seconds=getattr(tool, "timeout_seconds", None),
                            retry=getattr(tool, "retry", None),
                            auth=getattr(tool, "auth", None),
                            response_schema=getattr(tool, "response_schema", None),
                            logging=getattr(tool, "logging", None),
                            rate_limit=getattr(tool, "rate_limit", None),
                            multipart=getattr(tool, "multipart", False),
                            query_encoding=getattr(tool, "query_encoding", None),
                            query_template=getattr(tool, "query_template", None),
                            variables=getattr(tool, "variables", {}) or {},
                            function=getattr(tool, "function", None),
                        )
                    )

    def run_flow(
        self, flow: IRFlow, context: ExecutionContext, initial_state: Optional[dict[str, Any]] = None
    ) -> FlowRunResult:
        return asyncio.run(self.run_flow_async(flow, context, initial_state=initial_state))

    async def run_flow_async(
        self,
        flow: IRFlow,
        context: ExecutionContext,
        initial_state: Optional[dict[str, Any]] = None,
        stream_callback: Any = None,
    ) -> FlowRunResult:
        plan = _phases_prepare(
            self,
            flow,
            context,
            initial_state=initial_state,
            stream_callback=stream_callback,
        )
        result = await _phases_execute(self, plan)
        return _phases_finalize(self, plan, result)


__all__ = ["FlowEngine"]
