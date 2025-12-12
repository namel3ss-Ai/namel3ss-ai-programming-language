from __future__ import annotations

import asyncio
import importlib
import inspect
import json
import logging
import random
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

from ... import ast_nodes
from ...errors import Namel3ssError
from ...runtime.expressions import ExpressionEvaluator, VariableEnvironment
from ...tools.observability import after_tool_call, before_tool_call
from ...tools.registry import DEFAULT_TOOL_TIMEOUT_SECONDS
from ...tools.runtime import (
    apply_auth_config,
    build_multipart_body,
    build_tool_result,
    encode_query_items,
    format_tool_error,
    rate_limiter,
    validate_response_schema,
)
from ..graph import FlowRuntimeContext, FlowState

logger = logging.getLogger("namel3ss.flows.engine")

__all__ = [
    "_http_json_request",
    "_coerce_tool_timeout",
    "_allow_retry_for_method",
    "_should_retry_exception",
    "_compute_tool_retry_delay",
    "_sleep_tool_retry",
    "_apply_tool_auth",
    "_resolve_local_function",
    "_execute_local_function",
    "_execute_tool_call",
]


def _http_json_request(
    self, method: str, url: str, headers: dict[str, str], body: bytes | None, timeout: float | None = None
) -> tuple[int, dict[str, str], str]:
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:  # pragma: no cover - exercised via monkeypatch in tests
        with urllib.request.urlopen(req, timeout=timeout or DEFAULT_TOOL_TIMEOUT_SECONDS) as resp:
            text = resp.read().decode("utf-8", errors="replace")
            status = resp.getcode()
            resp_headers = dict(resp.headers.items())
            return status, resp_headers, text
    except urllib.error.HTTPError as exc:  # pragma: no cover - fallback
        text = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        resp_headers = dict(exc.headers.items()) if exc.headers else {}
        return exc.code, resp_headers, text


def _coerce_tool_timeout(self, value: Any, tool_name: str) -> float:
    if value is None:
        return DEFAULT_TOOL_TIMEOUT_SECONDS
    try:
        timeout_val = float(value)
    except Exception as exc:  # pragma: no cover - defensive
        raise Namel3ssError(f"Timeout for tool '{tool_name}' must be a number of seconds.") from exc
    if timeout_val <= 0:
        raise Namel3ssError(f"Timeout for tool '{tool_name}' must be greater than 0 seconds.")
    return timeout_val


def _allow_retry_for_method(self, method: str, retry_cfg: Any | None) -> bool:
    safe_methods = {"GET", "HEAD"}
    if method.upper() in safe_methods:
        return True
    return bool(getattr(retry_cfg, "allow_unsafe", False))


def _should_retry_exception(self, exc: BaseException, retry_cfg: Any | None) -> bool:
    if not retry_cfg:
        return False
    names = getattr(retry_cfg, "retry_on_exceptions", None) or []
    if not names:
        return False
    exc_name = exc.__class__.__name__
    return any(exc_name == name or exc_name.endswith(name) for name in names)


def _compute_tool_retry_delay(self, attempt: int, retry_cfg: Any | None) -> float:
    if not retry_cfg:
        return 0.0
    mode = (getattr(retry_cfg, "backoff", None) or "none").lower()
    base = getattr(retry_cfg, "initial_delay", None) or 0.0
    delay = 0.0
    if mode == "constant":
        delay = base
    elif mode == "exponential":
        delay = base * (2 ** max(attempt - 1, 0))
    if getattr(retry_cfg, "max_delay", None) is not None:
        delay = min(delay, getattr(retry_cfg, "max_delay", 0.0) or 0.0)
    if delay and getattr(retry_cfg, "jitter", False):
        delay = random.uniform(0, delay)
    return max(delay, 0.0)


async def _sleep_tool_retry(self, attempt: int, retry_cfg: Any | None) -> None:
    delay = self._compute_tool_retry_delay(attempt, retry_cfg)
    if delay > 0:
        await asyncio.sleep(delay)


def _apply_tool_auth(
    self,
    auth_cfg: Any,
    url: str,
    headers: dict[str, str],
    eval_value: Callable[[Any], Any],
    tool_name: str,
) -> tuple[str, dict[str, str]]:
    return apply_auth_config(auth_cfg, url, headers, eval_value, tool_name)


def _resolve_local_function(self, tool_cfg: Any):
    fn = getattr(tool_cfg, "local_function", None)
    if fn:
        return fn
    func_path = getattr(tool_cfg, "function", None)
    if not func_path:
        raise Namel3ssError(f"Tool '{getattr(tool_cfg, 'name', 'tool')}' is missing function path.")
    if "." not in func_path:
        raise Namel3ssError(f"Tool '{getattr(tool_cfg, 'name', 'tool')}' function path must include module and attribute.")
    module_name, _, attr = func_path.rpartition(".")
    try:
        module = importlib.import_module(module_name)
        fn = getattr(module, attr)
    except Exception as exc:
        raise Namel3ssError(f"Failed to import local_function '{func_path}': {exc}") from exc
    setattr(tool_cfg, "local_function", fn)
    return fn


def _execute_local_function(self, tool_cfg: Any, arg_values: dict[str, Any]) -> dict[str, Any]:
    fn = self._resolve_local_function(tool_cfg)
    try:
        try:
            result_val = fn(**arg_values)
        except TypeError:
            result_val = fn(arg_values)
        ok = True
    except Exception as exc:
        error_msg = f"Local function tool '{getattr(tool_cfg, 'name', 'tool')}' failed: {exc}"
        return {"ok": False, "status": None, "data": None, "headers": {}, "error": error_msg}
    schema = getattr(tool_cfg, "response_schema", None)
    if schema:
        valid, schema_error = validate_response_schema(schema, result_val)
        if not valid:
            err = format_tool_error(
                getattr(tool_cfg, "name", "tool"),
                "LOCAL",
                getattr(tool_cfg, "function", "") or getattr(tool_cfg, "name", "tool"),
                None,
                f"Response schema validation failed: {schema_error}",
            )
            return {"ok": False, "status": None, "data": result_val, "headers": {}, "error": err}
    return {"ok": ok, "status": None, "data": result_val, "headers": {}}


async def _execute_tool_call(self, node, state: FlowState, runtime_ctx: FlowRuntimeContext, tool_override=None):
    target = node.config.get("target") if isinstance(node.config, dict) else None
    tool_cfg = tool_override or runtime_ctx.tool_registry.get(target)
    if not tool_cfg:
        raise Namel3ssError(f'I couldn\'t find a tool named "{target}". Check your configuration or plugin setup.')

    evaluator = self._build_evaluator(state, runtime_ctx)
    params = node.config.get("params") or {}
    args_exprs = params.get("input") or params.get("args") or {}
    arg_values: dict[str, Any] = {}
    if isinstance(args_exprs, dict):
        for k, expr in args_exprs.items():
            try:
                if isinstance(expr, ast_nodes.Expr):
                    arg_values[k] = evaluator.evaluate(expr)
                else:
                    arg_values[k] = expr
            except Exception as exc:
                raise Namel3ssError(f"Failed to evaluate input '{k}' for tool '{tool_cfg.name}': {exc}") from exc
    if not arg_values:
        default_message = state.get("last_output")
        if default_message is None:
            default_message = state.get("slug")
        arg_values = {"message": default_message}

    required_inputs = list(getattr(tool_cfg, "input_fields", []) or [])
    missing_inputs = [field for field in required_inputs if field not in arg_values]
    if missing_inputs:
        raise Namel3ssError(
            f"N3F-965: Missing arg '{missing_inputs[0]}' for tool '{tool_cfg.name}'."
        )

    if (getattr(tool_cfg, "kind", "") or "").lower() == "local_function":
        return self._execute_local_function(tool_cfg, arg_values)

    if hasattr(tool_cfg, "calls"):
        payload = arg_values if arg_values else {"message": state.get("slug")}
        try:
            tool_cfg.calls.append(payload)
        except Exception:
            pass

    if getattr(tool_cfg, "url_expr", None) is None and getattr(tool_cfg, "url_template", None) is None:
        if callable(getattr(tool_cfg, "execute", None)):
            return tool_cfg.execute(arg_values)
        if callable(tool_cfg):
            return tool_cfg(arg_values)
        return {"result": arg_values}

    env = state.variables.clone() if state.variables else VariableEnvironment()
    if env.has("input"):
        env.assign("input", arg_values)
    else:
        env.declare("input", arg_values)
    tool_evaluator = self._build_evaluator(state, runtime_ctx, env_override=env)

    def _eval_value(expr: Any) -> Any:
        if isinstance(expr, ast_nodes.Expr):
            return tool_evaluator.evaluate(expr)
        return expr

    method = (getattr(tool_cfg, "method", "GET") or "GET").upper()
    kind_lower = (getattr(tool_cfg, "kind", "") or "").lower()
    if kind_lower == "graphql":
        method = "POST"

    url_value: Any = None
    if getattr(tool_cfg, "url_expr", None) is not None:
        url_value = _eval_value(tool_cfg.url_expr)
    else:
        url_template = getattr(tool_cfg, "url_template", None)
        if url_template:
            try:
                url_value = url_template.format(**{k: "" if v is None else str(v) for k, v in arg_values.items()})
            except KeyError as exc:
                missing = str(exc).strip("'\"")
                raise Namel3ssError(
                    f"N3F-965: Missing arg '{missing}' for tool '{tool_cfg.name}' url."
                )
    if not url_value:
        raise Namel3ssError(f"N3F-965: Tool '{tool_cfg.name}' is missing a resolved URL.")
    url_str = str(url_value)

    headers: dict[str, str] = {}
    for hk, h_expr in (getattr(tool_cfg, "headers", {}) or {}).items():
        value = _eval_value(h_expr)
        if value is None:
            continue
        headers[hk] = "" if value is None else str(value)

    query_exprs = getattr(tool_cfg, "query_params", {}) or {}
    if query_exprs:
        parsed = urllib.parse.urlparse(url_str)
        query_items = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        query_mode = getattr(tool_cfg, "query_encoding", None) or "repeat"
        for qk, q_expr in query_exprs.items():
            val = _eval_value(q_expr)
            if val is None:
                continue
            query_items.extend(encode_query_items(qk, val, query_mode))
        url_str = urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query_items, doseq=True)))

    body_payload: Any = None
    body_fields = getattr(tool_cfg, "body_fields", {}) or {}
    if body_fields:
        body_payload = {}
        for bk, b_expr in body_fields.items():
            body_payload[bk] = _eval_value(b_expr)
    elif getattr(tool_cfg, "body_template", None) is not None:
        body_payload = tool_evaluator.evaluate(tool_cfg.body_template)
    if kind_lower == "graphql":
        query_val = _eval_value(getattr(tool_cfg, "query_template", None))
        query_str = "" if query_val is None else str(query_val)
        var_payload: dict[str, Any] = {}
        for vk, v_expr in (getattr(tool_cfg, "variables", {}) or {}).items():
            var_payload[vk] = _eval_value(v_expr)
        body_payload = {"query": query_str}
        if var_payload:
            body_payload["variables"] = var_payload
        headers.setdefault("Content-Type", "application/json")

    body_bytes: bytes | None = None
    is_multipart = bool(getattr(tool_cfg, "multipart", False))
    if is_multipart:
        if body_payload is None:
            body_payload = {}
        if not isinstance(body_payload, dict):
            raise Namel3ssError(f"Tool '{tool_cfg.name}' multipart body must be a record/object.")
        body_bytes, content_type = build_multipart_body(body_payload)
        headers["Content-Type"] = content_type
    elif body_payload is not None:
        if isinstance(body_payload, (dict, list)):
            body_bytes = json.dumps(body_payload).encode("utf-8")
            headers.setdefault("Content-Type", "application/json")
        elif isinstance(body_payload, str):
            body_bytes = body_payload.encode("utf-8")
        else:
            body_bytes = json.dumps(body_payload).encode("utf-8")
            headers.setdefault("Content-Type", "application/json")

    timeout_override_expr = node.config.get("timeout") if isinstance(node.config, dict) else None
    timeout_seconds = getattr(tool_cfg, "timeout_seconds", None)
    if timeout_seconds is None:
        timeout_seconds = DEFAULT_TOOL_TIMEOUT_SECONDS
    if timeout_override_expr is not None:
        try:
            override_val = _eval_value(timeout_override_expr)
        except Exception as exc:
            raise Namel3ssError(f"Failed to evaluate timeout for tool '{tool_cfg.name}': {exc}") from exc
        if override_val is not None:
            timeout_seconds = self._coerce_tool_timeout(override_val, tool_cfg.name)

    auth_cfg = getattr(tool_cfg, "auth", None)
    try:
        url_str, headers = self._apply_tool_auth(auth_cfg, url_str, headers, _eval_value, tool_cfg.name)
    except Namel3ssError:
        raise
    except Exception as exc:
        raise Namel3ssError(f"Failed to apply auth for tool '{tool_cfg.name}': {exc}") from exc

    retry_cfg = getattr(tool_cfg, "retry", None)
    max_attempts = getattr(retry_cfg, "max_attempts", 1) if retry_cfg else 1
    if max_attempts is None or max_attempts < 1:
        max_attempts = 1
    can_retry = self._allow_retry_for_method(method, retry_cfg)
    if not can_retry:
        max_attempts = 1

    rate_cfg = getattr(tool_cfg, "rate_limit", None)
    if rate_cfg:
        allowed = rate_limiter.allow(
            getattr(tool_cfg, "name", "tool"),
            getattr(rate_cfg, "max_calls_per_minute", None),
            getattr(rate_cfg, "max_calls_per_second", None),
            getattr(rate_cfg, "burst", None),
        )
        if not allowed:
            desc_parts = []
            if getattr(rate_cfg, "max_calls_per_second", None) is not None:
                desc_parts.append(f"{rate_cfg.max_calls_per_second} calls/second")
            if getattr(rate_cfg, "max_calls_per_minute", None) is not None:
                desc_parts.append(f"{rate_cfg.max_calls_per_minute} calls/minute")
            if getattr(rate_cfg, "burst", None) is not None:
                desc_parts.append(f"burst {rate_cfg.burst}")
            reason = "rate limit exceeded"
            if desc_parts:
                reason += f" ({', '.join(desc_parts)})"
            error_msg = format_tool_error(tool_cfg.name, method, url_str, None, reason)
            return {
                "ok": False,
                "status": None,
                "data": None,
                "headers": {},
                "error": error_msg,
            }

    request_info = {
        "method": method,
        "url": url_str,
        "headers": dict(headers),
        "body": body_payload,
        "timeout": timeout_seconds,
    }
    try:
        before_tool_call(tool_cfg, request_info)
    except Exception:
        logger.debug("before_tool_call interceptor failed", exc_info=True)

    if runtime_ctx.event_logger:
        try:
            runtime_ctx.event_logger.log(
                {
                    "kind": "tool",
                    "event_type": "start",
                    "tool": tool_cfg.name,
                    "step": node.id,
                    "flow_name": state.context.get("flow_name"),
                    "status": "running",
                    "method": method,
                    "url": url_str,
                }
            )
        except Exception:
            pass

    async def _do_request() -> tuple[int, dict[str, str], str]:
        # Support both sync and async transports; offload sync calls to a thread.
        if inspect.iscoroutinefunction(self._http_json_request):
            return await self._http_json_request(method, url_str, headers, body_bytes, timeout_seconds)
        return await asyncio.to_thread(
            self._http_json_request, method, url_str, headers, body_bytes, timeout_seconds
        )

    status: int | None = None
    response_headers: dict[str, str] = {}
    raw_text = ""
    try:
        attempt = 0
        while attempt < max_attempts:
            attempt += 1
            try:
                status, response_headers, raw_text = await _do_request()
            except Exception as exc:
                if not (can_retry and self._should_retry_exception(exc, retry_cfg)) or attempt >= max_attempts:
                    raise
                await self._sleep_tool_retry(attempt, retry_cfg)
                continue
            if (
                can_retry
                and retry_cfg
                and getattr(retry_cfg, "retry_on_status", None)
                and status is not None
                and status in (retry_cfg.retry_on_status or [])
                and attempt < max_attempts
            ):
                await self._sleep_tool_retry(attempt, retry_cfg)
                continue
            break
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        error_msg = format_tool_error(
            getattr(tool_cfg, "name", "tool"),
            method,
            url_str,
            None,
            f"Network error: {getattr(exc, 'reason', exc)}",
        )
        result = {
            "ok": False,
            "status": None,
            "data": None,
            "headers": {},
            "error": error_msg,
        }
        try:
            after_tool_call(
                tool_cfg,
                {
                    "ok": False,
                    "status": None,
                    "error": error_msg,
                    "method": method,
                    "url": url_str,
                    "headers": {},
                    "raw_text": raw_text,
                },
            )
        except Exception:
            logger.debug("after_tool_call interceptor failed", exc_info=True)
        if runtime_ctx.event_logger:
            try:
                runtime_ctx.event_logger.log(
                    {
                        "kind": "tool",
                        "event_type": "error",
                        "tool": tool_cfg.name,
                        "step": node.id,
                        "flow_name": state.context.get("flow_name"),
                        "status": "error",
                        "message": error_msg,
                    }
                )
            except Exception:
                pass
        return result

    parsed_body: Any = None
    if raw_text:
        try:
            parsed_body = json.loads(raw_text)
        except ValueError:
            parsed_body = raw_text

    result = build_tool_result(tool_cfg, method, url_str, status, parsed_body, response_headers, raw_text)
    if kind_lower == "graphql" and isinstance(parsed_body, dict) and parsed_body.get("errors"):
        msg = parsed_body.get("errors")
        snippet = None
        if isinstance(msg, list) and msg:
            first = msg[0]
            if isinstance(first, dict) and first.get("message"):
                snippet = first.get("message")
            else:
                snippet = str(first)
        error_reason = f"GraphQL errors: {snippet or 'see response'}"
        result["ok"] = False
        result["error"] = format_tool_error(tool_cfg.name, method, url_str, status, error_reason, raw_text)
    ok = bool(result.get("ok"))

    try:
        after_tool_call(
            tool_cfg,
            {
                "ok": ok,
                "status": status,
                "error": result.get("error"),
                "method": method,
                "url": url_str,
                "headers": response_headers,
                "raw_text": raw_text,
                "data": parsed_body,
            },
        )
    except Exception:
        logger.debug("after_tool_call interceptor failed", exc_info=True)

    if runtime_ctx.event_logger:
        try:
            runtime_ctx.event_logger.log(
                {
                    "kind": "tool",
                    "event_type": "end" if ok else "error",
                    "tool": tool_cfg.name,
                    "step": node.id,
                    "flow_name": state.context.get("flow_name"),
                    "status": "success" if ok else "error",
                    "status_code": status,
                    "method": method,
                    "url": url_str,
                    "ok": ok,
                }
            )
        except Exception:
            pass
    return result
