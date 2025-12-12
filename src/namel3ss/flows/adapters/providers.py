from __future__ import annotations

import asyncio
import time
import urllib.error
from typing import Any

from ...ai.registry import ModelRegistry
from ...errors import (
    Namel3ssError,
    ProviderAuthError,
    ProviderCircuitOpenError,
    ProviderConfigError,
    ProviderRetryError,
    ProviderTimeoutError,
)
from ...observability.metrics import default_metrics
from ...observability.tracing import default_tracer
from ...runtime.retries import with_retries_and_timeout
from ..state.context import (
    ExecutionContext,
    _apply_conversation_summary_if_needed,
    _build_vector_context_messages,
    _upsert_vector_memory,
    build_memory_messages,
    execute_ai_call_with_registry,
    get_vector_memory_settings,
    persist_memory_state,
    run_memory_pipelines,
)
from ..graph import FlowRuntimeContext
from ..models import StreamEvent

__all__ = ["_call_ai_step", "_stream_ai_step"]


async def _call_ai_step(
    self,
    ai_call,
    base_context: ExecutionContext,
    runtime_ctx: FlowRuntimeContext,
    step_name: str,
    flow_name: str,
    tools_mode: str | None = None,
) -> Any:
    provider, provider_model, provider_name = runtime_ctx.model_registry.resolve_provider_for_ai(ai_call)
    provider_model = provider_model or ai_call.model_name or provider_name
    provider_key = f"model:{provider_name}:{provider_model}"
    start_time = time.monotonic()
    retries = 0
    last_error_type: str | None = None
    tracer_instance = runtime_ctx.tracer or default_tracer
    event_logger = runtime_ctx.event_logger
    if event_logger:
        try:
            event_logger.log(
                {
                    "kind": "provider",
                    "event_type": "provider_call_start",
                    "flow_name": flow_name,
                    "step_name": step_name,
                    "provider": provider_name,
                    "model": provider_model,
                    "status": "running",
                }
            )
        except Exception:
            pass

    def _on_error(exc: BaseException, attempt: int) -> None:
        nonlocal retries, last_error_type
        retries = max(retries, attempt + 1)
        last_error_type = exc.__class__.__name__

    async def _invoke() -> Any:
        return await asyncio.to_thread(
            execute_ai_call_with_registry,
            ai_call,
            runtime_ctx.model_registry,
            runtime_ctx.router,
            base_context,
            tools_mode,
        )

    status = "success"
    with tracer_instance.span(
        "provider.call",
        attributes={
            "provider": provider_name,
            "model": provider_model,
            "flow": flow_name,
            "step": step_name,
        },
    ):
        try:
            return await with_retries_and_timeout(
                _invoke,
                config=self.retry_config,
                error_types=self.retry_error_types,
                on_error=_on_error,
                circuit_breaker=self.circuit_breaker,
                provider_key=provider_key,
            )
        except ProviderCircuitOpenError as exc:
            status = "circuit_open"
            last_error_type = exc.__class__.__name__
            raise
        except ProviderTimeoutError as exc:
            status = "timeout"
            last_error_type = exc.__class__.__name__
            raise
        except ProviderRetryError as exc:
            status = "failure"
            last_error_type = exc.__class__.__name__
            raise
        except Exception as exc:
            status = "failure"
            last_error_type = exc.__class__.__name__
            raise
        finally:
            duration = time.monotonic() - start_time
            try:
                default_metrics.record_provider_call(provider_name, provider_model, status, duration)
                if status == "circuit_open":
                    default_metrics.record_circuit_open(provider_name)
            except Exception:
                pass
            if event_logger:
                try:
                    event_logger.log(
                        {
                            "kind": "provider",
                            "event_type": "provider_call_end",
                            "flow_name": flow_name,
                            "step_name": step_name,
                            "provider": provider_name,
                            "model": provider_model,
                            "status": status,
                            "duration": duration,
                            "retries": retries,
                            "error_type": last_error_type,
                        }
                    )
                except Exception:
                    pass


async def _stream_ai_step(
    self,
    ai_call,
    base_context: ExecutionContext,
    runtime_ctx: FlowRuntimeContext,
    step_name: str,
    flow_name: str,
    stream_meta: dict[str, object] | None = None,
    tools_mode: str | None = None,
):
    provider, provider_model, provider_name = runtime_ctx.model_registry.resolve_provider_for_ai(ai_call)
    provider_model = provider_model or ai_call.model_name
    provider_key = f"model:{provider_name}:{provider_model}"
    tracer_instance = runtime_ctx.tracer or default_tracer
    event_logger = runtime_ctx.event_logger
    status = "success"
    last_error_type: str | None = None
    start_time = time.monotonic()
    vector_enabled, vector_store_name, vector_top_k = get_vector_memory_settings()
    vector_registry = getattr(base_context, "vectorstores", None)
    if event_logger:
        try:
            event_logger.log(
                {
                    "kind": "provider",
                    "event_type": "provider_call_start",
                    "flow_name": flow_name,
                    "step_name": step_name,
                    "provider": provider_name,
                    "model": provider_model,
                    "status": "running",
                    "streaming": True,
                }
            )
        except Exception:
            pass
    if self.circuit_breaker and not self.circuit_breaker.should_allow_call(provider_key):
        status = "circuit_open"
        last_error_type = "ProviderCircuitOpenError"
        duration = time.monotonic() - start_time
        try:
            default_metrics.record_provider_call(provider_name, provider_model, status, duration)
            default_metrics.record_circuit_open(provider_name)
        except Exception:
            pass
        if event_logger:
            try:
                event_logger.log(
                    {
                        "kind": "provider",
                        "event_type": "provider_call_end",
                        "flow_name": flow_name,
                        "step_name": step_name,
                        "provider": provider_name,
                        "model": provider_model,
                        "status": status,
                        "duration": duration,
                        "retries": 0,
                        "error_type": last_error_type,
                        "streaming": True,
                    }
                )
            except Exception:
                pass
        raise ProviderCircuitOpenError(f"Circuit open for provider '{provider_key}'.")
    messages: list[dict[str, str]] = []

    session_id = base_context.metadata.get("session_id") if base_context.metadata else None
    session_id = session_id or base_context.request_id or "default"
    metadata_user_id = base_context.metadata.get("user_id") if base_context.metadata else None
    user_id = str(metadata_user_id) if metadata_user_id is not None else None

    if getattr(ai_call, "system_prompt", None):
        messages.append({"role": "system", "content": ai_call.system_prompt or ""})

    memory_cfg = getattr(ai_call, "memory", None)
    memory_state: dict[str, Any] | None = None
    if memory_cfg and getattr(base_context, "memory_stores", None):
        memory_state, memory_messages = build_memory_messages(ai_call, base_context, session_id, user_id)
        messages.extend(memory_messages)
    elif getattr(ai_call, "memory_name", None) and base_context.memory_engine:
        try:
            history = base_context.memory_engine.load_conversation(ai_call.memory_name or "", session_id=session_id)
            messages.extend(history)
        except Exception:
            raise Namel3ssError(
                f"Failed to load conversation history for memory '{ai_call.memory_name}'."
            )

    user_content = ai_call.input_source or (base_context.user_input or "")
    vector_context_messages: list[dict[str, str]] = []
    if vector_enabled:
        if not vector_registry:
            raise ProviderConfigError("Vector memory is enabled but no vector store registry is configured.")
        try:
            vector_context_messages = _build_vector_context_messages(
                vector_registry,
                user_content,
                vector_store_name,
                vector_top_k,
            )
        except Exception as exc:
            raise ProviderConfigError(
                f"Vector memory store '{vector_store_name}' is unavailable or misconfigured: {exc}"
            ) from exc
    if vector_context_messages:
        messages.extend(vector_context_messages)
    user_message = {"role": "user", "content": user_content}
    messages.append(user_message)
    messages = _apply_conversation_summary_if_needed(messages, provider, provider_model, provider_name)

    if getattr(ai_call, "tools", None):
        requested_mode = (tools_mode or "auto").lower()
        if requested_mode != "none":
            raise Namel3ssError(
                f"N3F-975: Streaming AI steps do not support tool calling (AI '{ai_call.name}'). "
                "Disable streaming or set 'tools is \"none\"' on the step."
            )
    tools_payload = None

    full_text = ""
    mode = "tokens"
    channel = None
    role = None
    label = None
    if stream_meta:
        channel = stream_meta.get("channel")
        role = stream_meta.get("role")
        label = stream_meta.get("label")
        mode_candidate = stream_meta.get("mode") or mode
        if isinstance(mode_candidate, str):
            mode_candidate = mode_candidate or mode
        else:
            mode_candidate = str(mode_candidate)
        if mode_candidate in {"tokens", "sentences", "full"}:
            mode = mode_candidate
    sentence_buffer = ""

    async def emit(kind: str, **payload):
        event: StreamEvent = {
            "kind": kind,
            "flow": flow_name,
            "step": step_name,
            "channel": channel,
            "role": role,
            "label": label,
            "mode": mode,
        }
        event.update(payload)
        if runtime_ctx.stream_callback:
            await runtime_ctx.stream_callback(event)

    async def _flush_sentence_chunks(buffer: str, force: bool = False) -> str:
        remaining = buffer
        while True:
            boundary_idx = None
            for idx, ch in enumerate(remaining):
                if ch in ".!?":
                    next_char = remaining[idx + 1] if idx + 1 < len(remaining) else ""
                    if not next_char or next_char.isspace():
                        boundary_idx = idx
                        break
            if boundary_idx is None:
                break
            segment = remaining[: boundary_idx + 1]
            remaining = remaining[boundary_idx + 1 :]
            if segment.strip():
                await emit("chunk", delta=segment)
            remaining = remaining.lstrip()
        if force and remaining.strip():
            await emit("chunk", delta=remaining)
            remaining = ""
        return remaining

    with tracer_instance.span(
        "provider.call",
        attributes={
            "provider": provider_name,
            "model": provider_model,
            "flow": flow_name,
            "step": step_name,
            "streaming": True,
        },
    ):
        try:
            for chunk in provider.stream(messages=messages, model=provider_model, tools=tools_payload):
                delta = ""
                if isinstance(chunk, dict):
                    delta = chunk.get("delta") or ""
                else:
                    delta = getattr(chunk, "delta", "") or ""
                if delta:
                    delta_str = str(delta)
                    full_text += delta_str
                    if mode == "tokens":
                        await emit("chunk", delta=delta_str)
                    elif mode == "sentences":
                        sentence_buffer += delta_str
                        sentence_buffer = await _flush_sentence_chunks(sentence_buffer, force=False)
                    # mode == "full" defers emission until the end
            runtime_ctx.model_registry.provider_status[provider_name] = "ok"
            ModelRegistry.last_status[provider_name] = "ok"
            if self.circuit_breaker:
                self.circuit_breaker.record_success(provider_key)
            if mode == "sentences":
                sentence_buffer = await _flush_sentence_chunks(sentence_buffer, force=True)
            await emit("done", full=full_text)
        except urllib.error.HTTPError as exc:
            status = "failure"
            last_error_type = exc.__class__.__name__
            if self.circuit_breaker:
                self.circuit_breaker.record_failure(provider_key, exc)
            if exc.code in {401, 403}:
                runtime_ctx.model_registry.provider_status[provider_name] = "unauthorized"
                ModelRegistry.last_status[provider_name] = "unauthorized"
                auth_err = ProviderAuthError(
                    f"Provider '{provider_name}' rejected the API key (unauthorized). Check your key and account permissions.",
                    code="N3P-1802",
                )
                await emit("error", error=str(auth_err), code=auth_err.code)
                raise auth_err
            await emit("error", error=str(exc), code=getattr(exc, "code", None))
            raise
        except ProviderConfigError as exc:
            status = "failure"
            last_error_type = exc.__class__.__name__
            if self.circuit_breaker:
                self.circuit_breaker.record_failure(provider_key, exc)
            await emit("error", error=str(exc), code=exc.code)
            raise
        except Exception as exc:
            status = "failure"
            last_error_type = exc.__class__.__name__
            if self.circuit_breaker:
                self.circuit_breaker.record_failure(provider_key, exc)
            await emit("error", error=str(exc), code=getattr(exc, "code", None))
            raise
        finally:
            duration = time.monotonic() - start_time
            try:
                default_metrics.record_provider_call(provider_name, provider_model, status, duration)
                if status == "circuit_open":
                    default_metrics.record_circuit_open(provider_name)
            except Exception:
                pass
            if event_logger:
                try:
                    event_logger.log(
                        {
                            "kind": "provider",
                            "event_type": "provider_call_end",
                            "flow_name": flow_name,
                            "step_name": step_name,
                            "provider": provider_name,
                            "model": provider_model,
                            "status": status,
                            "duration": duration,
                            "retries": 0,
                            "error_type": last_error_type,
                            "streaming": True,
                        }
                    )
                except Exception:
                    pass

    if memory_state:
        persist_memory_state(memory_state, ai_call, session_id, user_content, full_text, user_id)
        run_memory_pipelines(
            ai_call,
            memory_state,
            session_id,
            user_content,
            full_text,
            user_id,
            provider,
            provider_model,
        )
    elif getattr(ai_call, "memory_name", None) and base_context.memory_engine:
        try:
            base_context.memory_engine.append_conversation(
                ai_call.memory_name or "",
                messages=[
                    user_message,
                    {"role": "assistant", "content": full_text},
                ],
                session_id=session_id,
            )
        except Exception:
            pass
    if vector_enabled:
        if not vector_registry:
            raise ProviderConfigError("Vector memory is enabled but no vector store registry is configured.")
        try:
            _upsert_vector_memory(
                vector_registry,
                vector_store_name,
                [user_message, {"role": "assistant", "content": full_text}],
                metadata={"session_id": session_id, "ai": ai_call.name, "user_id": user_id},
            )
        except Exception as exc:
            raise ProviderConfigError(
                f"Vector memory store '{vector_store_name}' is unavailable or misconfigured: {exc}"
            ) from exc
    return full_text
