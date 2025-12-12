from __future__ import annotations

from typing import Any

from ...errors import Namel3ssError
from ..graph import FlowNode, FlowRuntimeContext, FlowState
from ..state.context import ExecutionContext

__all__ = ["_run_ai_step"]


async def _run_ai_step(
    self,
    node: FlowNode,
    state: FlowState,
    runtime_ctx: FlowRuntimeContext,
    base_context: ExecutionContext,
    step_name: str,
    target: str | None,
    params: dict[str, Any],
) -> Any:
    if not target:
        raise Namel3ssError("This AI step needs a target (the model to call), but none was provided.")
    if target not in runtime_ctx.program.ai_calls:
        raise Namel3ssError(f'I couldn\'t find an AI call named \"{target}\". Check your configuration or plugin setup.')
    ai_call = runtime_ctx.program.ai_calls[target]
    if runtime_ctx.event_logger:
        try:
            runtime_ctx.event_logger.log(
                {
                    "kind": "ai",
                    "event_type": "start",
                    "flow_name": state.context.get("flow_name"),
                    "step_name": step_name,
                    "ai_name": ai_call.name,
                    "model": ai_call.model_name,
                    "status": "running",
                }
            )
        except Exception:
            pass
    stream_cfg = node.config.get("stream") or {}
    streaming = bool(stream_cfg.get("streaming")) or bool(params.get("streaming"))
    mode_val = stream_cfg.get("stream_mode") or params.get("stream_mode") or "tokens"
    if isinstance(mode_val, str):
        mode_val = mode_val or "tokens"
    else:
        mode_val = str(mode_val)
    if mode_val not in {"tokens", "sentences", "full"}:
        mode_val = "tokens"
    stream_meta = {
        "channel": stream_cfg.get("stream_channel") or params.get("stream_channel"),
        "role": stream_cfg.get("stream_role") or params.get("stream_role"),
        "label": stream_cfg.get("stream_label") or params.get("stream_label"),
        "mode": mode_val,
    }
    tools_mode = node.config.get("tools_mode")
    if streaming:
        output = await self._stream_ai_step(
            ai_call,
            base_context,
            runtime_ctx,
            step_name=step_name,
            flow_name=state.context.get("flow_name") or "",
            stream_meta=stream_meta,
            tools_mode=tools_mode,
        )
    else:
        output = await self._call_ai_step(
            ai_call=ai_call,
            base_context=base_context,
            runtime_ctx=runtime_ctx,
            step_name=step_name,
            flow_name=state.context.get("flow_name") or "",
            tools_mode=tools_mode,
        )
    if runtime_ctx.event_logger:
        try:
            runtime_ctx.event_logger.log(
                {
                    "kind": "ai",
                    "event_type": "end",
                    "flow_name": state.context.get("flow_name"),
                    "step_name": step_name,
                    "ai_name": ai_call.name,
                    "model": ai_call.model_name,
                    "status": "success",
                }
            )
        except Exception:
            pass
    return output
