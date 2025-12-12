from __future__ import annotations

from typing import Any
from uuid import uuid4

from ...errors import Namel3ssError
from ...runtime.auth import hash_password, verify_password
from ...runtime.expressions import ExpressionEvaluator
from ..graph import FlowRuntimeContext, FlowState

__all__ = ["FlowEngineAuthMixin"]


class FlowEngineAuthMixin:
    def _execute_auth_step(
        self,
        kind: str,
        auth_config: Any,
        record: Any,
        params: dict[str, Any],
        evaluator: ExpressionEvaluator,
        runtime_ctx: FlowRuntimeContext,
        step_name: str,
        state: FlowState,
    ) -> Any:
        frames = runtime_ctx.frames
        if frames is None:
            raise Namel3ssError("Frame registry unavailable for auth operations.")
        frame_name = getattr(record, "frame", None)
        if not frame_name:
            raise Namel3ssError("Auth user_record is missing an associated frame.")
        identifier_field = getattr(auth_config, "identifier_field", None)
        password_hash_field = getattr(auth_config, "password_hash_field", None)
        id_field = getattr(auth_config, "id_field", None) or getattr(record, "primary_key", None)
        if not identifier_field or not password_hash_field:
            raise Namel3ssError("Auth configuration is incomplete.")
        identifier_field_obj = record.fields.get(identifier_field)
        if not identifier_field_obj:
            raise Namel3ssError(f"Auth identifier_field '{identifier_field}' not found on user_record.")
        user_ctx = getattr(runtime_ctx, "user_context", None)
        if user_ctx is None:
            user_ctx = {"id": None, "is_authenticated": False, "record": None}
            runtime_ctx.user_context = user_ctx
        if "user" not in state.context or state.context.get("user") is None:
            state.context["user"] = user_ctx
        input_values = self._evaluate_expr_dict(params.get("input"), evaluator, step_name, "input")
        identifier_value = input_values.get(identifier_field)
        password_value = input_values.get("password")
        if kind == "auth_register":
            if identifier_value is None or password_value is None:
                raise Namel3ssError("Missing identifier or password for auth_register.")
            filters = {
                identifier_field: self._coerce_record_value(record.name, identifier_field_obj, identifier_value, step_name)
            }
            existing = frames.query(frame_name, filters)
            if existing:
                return {"ok": False, "code": "AUTH_USER_EXISTS", "error": "User already exists."}
            password_hash = hash_password(str(password_value))
            values: dict[str, Any] = {}
            for key, raw_val in input_values.items():
                if key == "password":
                    continue
                if key == password_hash_field:
                    continue
                values[key] = raw_val
            values[identifier_field] = identifier_value
            values[password_hash_field] = password_hash
            if id_field and id_field not in values:
                pk_field = record.fields.get(id_field)
                if pk_field and getattr(pk_field, "type", None) == "uuid":
                    values[id_field] = str(uuid4())
            normalized = self._prepare_record_values(
                record,
                values,
                step_name,
                include_defaults=True,
                enforce_required=True,
            )
            frames.insert(frame_name, normalized)
            return {"ok": True, "user_id": normalized.get(id_field), "user": dict(normalized)}
        if kind == "auth_login":
            if identifier_value is None or password_value is None:
                raise Namel3ssError("Missing identifier or password for auth_login.")
            filters = {
                identifier_field: self._coerce_record_value(record.name, identifier_field_obj, identifier_value, step_name)
            }
            rows = frames.query(frame_name, filters)
            if not rows:
                return {"ok": False, "code": "AUTH_INVALID_CREDENTIALS", "error": "Invalid credentials."}
            user_row = rows[0]
            stored_hash = user_row.get(password_hash_field)
            valid = False
            try:
                valid = verify_password(str(password_value), str(stored_hash or ""))
            except Namel3ssError as exc:
                raise Namel3ssError(str(exc))
            if not valid:
                return {"ok": False, "code": "AUTH_INVALID_CREDENTIALS", "error": "Invalid credentials."}
            user_id = user_row.get(id_field)
            user_ctx["id"] = user_id
            user_ctx["record"] = dict(user_row)
            user_ctx["is_authenticated"] = True
            if runtime_ctx.execution_context:
                runtime_ctx.execution_context.user_context = user_ctx
                if getattr(runtime_ctx.execution_context, "metadata", None) is not None:
                    runtime_ctx.execution_context.metadata["user_id"] = user_id
            return {"ok": True, "user_id": user_id, "user": dict(user_row)}
        if kind == "auth_logout":
            user_ctx["id"] = None
            user_ctx["record"] = None
            user_ctx["is_authenticated"] = False
            if runtime_ctx.execution_context and getattr(runtime_ctx.execution_context, "metadata", None) is not None:
                runtime_ctx.execution_context.metadata.pop("user_id", None)
                runtime_ctx.execution_context.user_context = user_ctx
            return {"ok": True}
        raise Namel3ssError(f"Unsupported auth operation '{kind}'.")
