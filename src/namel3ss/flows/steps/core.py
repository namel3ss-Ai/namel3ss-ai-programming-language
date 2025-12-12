from __future__ import annotations

from ... import ast_nodes
from ...errors import Namel3ssError
from ...runtime.expressions import build_missing_field_error
from ..graph import FlowNode

__all__ = ["FlowEngineCoreMixin"]


class FlowEngineCoreMixin:
    def _resolve_step_kind(self, node: FlowNode) -> str:
        cfg = node.config if isinstance(node.config, dict) else {}
        kind = node.kind or ""
        statements = cfg.get("statements") or []
        if not kind:
            if statements:
                return "script"
            return "script"
        builtin = {"script", "ai", "agent", "tool"}
        supported = builtin | {
            "condition",
            "branch",
            "join",
            "parallel",
            "for_each",
            "try",
            "goto_flow",
            "subflow",
            "rag",
            "vector",
            "vector_query",
            "vector_index_frame",
            "rag_query",
            "frame_insert",
            "frame_query",
            "frame_update",
            "frame_delete",
            "db_create",
            "db_update",
            "db_delete",
            "db_bulk_create",
            "db_bulk_update",
            "db_bulk_delete",
            "find",
            "auth_register",
            "auth_login",
            "auth_logout",
            "noop",
            "function",
            "transaction",
        }
        if kind in supported:
            return "script" if kind == "function" and statements else kind
        raise Namel3ssError(
            f'I don\'t know how to run a step with kind is "{kind}".\nSupported built-in kinds are "script", "ai", "agent", and "tool".'
        )

    def _apply_destructuring(self, pattern, value, env, state, *, is_constant: bool = False) -> None:
        if pattern.kind == "record":
            if not isinstance(value, dict):
                raise Namel3ssError("N3-3300: I can only destructure fields from a record value.")
            for field in pattern.fields:
                target_name = field.alias or field.name
                if field.name not in value:
                    raise Namel3ssError(
                        build_missing_field_error(
                            field.name,
                            value,
                            context=f"I can't destructure field {field.name} from this record.",
                        )
                    )
                env.declare(target_name, value.get(field.name), is_constant=is_constant)
                state.set(target_name, value.get(field.name))
            return
        if pattern.kind == "list":
            if not isinstance(value, (list, tuple)):
                raise Namel3ssError("Cannot destructure list; expected a list/sequence.")
            fields = pattern.fields
            if len(value) < len(fields):
                raise Namel3ssError(
                    f"Cannot destructure list into [{', '.join(fields)}]; it has only {len(value)} elements."
                )
            for idx, name in enumerate(fields):
                env.declare(name, value[idx] if idx < len(value) else None, is_constant=is_constant)
                state.set(name, value[idx] if idx < len(value) else None)
            return
        raise Namel3ssError("Unsupported destructuring pattern.")
