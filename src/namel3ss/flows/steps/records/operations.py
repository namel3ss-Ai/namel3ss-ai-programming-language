from __future__ import annotations

from typing import Any

from .... import ast_nodes
from ....errors import Namel3ssError
from ....ir import IRBulkCreateSpec, IRBulkDeleteSpec, IRBulkUpdateSpec, IRRecordQuery
from ...graph import FlowRuntimeContext
from ...graph import FlowState

__all__ = ["FlowEngineRecordOperationsMixin"]


class FlowEngineRecordOperationsMixin:
    def _evaluate_pagination_expr(
        self,
        expr: Any,
        evaluator,
        step_name: str,
        label: str,
        default: int | None = None,
    ) -> int | None:
        if expr is None:
            return default
        try:
            value = evaluator.evaluate(expr) if isinstance(expr, ast_nodes.Expr) else expr
        except Exception as exc:
            raise Namel3ssError(f"I expected a non-negative number for {label}, but couldn't evaluate it: {exc}") from exc
        if value is None:
            return default
        if not isinstance(value, (int, float)):
            raise Namel3ssError(
                f"I expected a non-negative number for {label}, but got {value} instead."
            )
        number = int(value)
        if number < 0:
            raise Namel3ssError(f"I expected a non-negative number for {label}, but got {value} instead.")
        return number

    def _execute_record_step(
        self,
        kind: str,
        record,
        params: dict[str, Any],
        evaluator,
        runtime_ctx: FlowRuntimeContext,
        step_name: str,
    ) -> Any:
        frames = runtime_ctx.frames
        if frames is None:
            raise Namel3ssError("Frame registry unavailable for record operations.")
        frame_name = getattr(record, "frame", None)
        if not frame_name:
            raise Namel3ssError(
                f"Record '{record.name}' is missing an associated frame."
            )
        if kind == "db_create":
            values = self._evaluate_expr_dict(params.get("values"), evaluator, step_name, "values")
            normalized = self._prepare_record_values(
                record,
                values,
                step_name,
                include_defaults=True,
                enforce_required=True,
            )
            self._validate_record_field_values(record, normalized)
            candidate_row = dict(normalized)
            self._enforce_record_uniqueness(
                record,
                candidate_row,
                None,
                frames,
                frame_name,
                operation="create",
            )
            self._enforce_record_foreign_keys(
                record,
                candidate_row,
                None,
                frames,
                getattr(runtime_ctx, "records", None),
                operation="create",
            )
            frames.insert(frame_name, normalized)
            return dict(normalized)
        if kind == "db_bulk_create":
            bulk_spec = params.get("bulk_create")
            if not isinstance(bulk_spec, IRBulkCreateSpec):
                raise Namel3ssError("I need create many ... details to run this bulk create step.")
            expr_label = self._expr_to_str(bulk_spec.source_expr)
            source_label = f"create many {record.name} from {expr_label or 'that expression'}"
            source_value = self._evaluate_bulk_source(bulk_spec.source_expr, evaluator, step_name, source_label)
            if not source_value:
                return []
            local_uniques: dict[tuple[str, Any | None], set[Any]] = {}
            runtime_records = getattr(runtime_ctx, "records", None)
            prepared_rows: list[dict[str, Any]] = []
            for idx, item in enumerate(source_value, start=1):
                if not isinstance(item, dict):
                    raise Namel3ssError(
                        f"Item {idx} inside create many {record.name} must be a record of field values, but I received {type(item).__name__}."
                    )
                normalized = self._prepare_record_values(
                    record,
                    item,
                    step_name,
                    include_defaults=True,
                    enforce_required=True,
                )
                self._validate_record_field_values(record, normalized)
                candidate_row = dict(normalized)
                self._enforce_record_uniqueness(
                    record,
                    candidate_row,
                    None,
                    frames,
                    frame_name,
                    operation="create",
                )
                self._enforce_record_foreign_keys(
                    record,
                    candidate_row,
                    None,
                    frames,
                    runtime_records,
                    operation="create",
                )
                self._track_pending_uniques(record, candidate_row, local_uniques)
                prepared_rows.append(normalized)
            inserted_rows: list[dict[str, Any]] = []
            for row in prepared_rows:
                frames.insert(frame_name, row)
                inserted_rows.append(dict(row))
            return inserted_rows
        if kind in {"find", "db_get"}:
            query_obj = params.get("query")
            alias = record.name.lower()
            where_values = None
            order_values = None
            limit_expr = None
            offset_expr = None
            filters_tree = None
            if isinstance(query_obj, IRRecordQuery):
                alias = query_obj.alias or alias
                where_values = query_obj.where_condition
                order_values = query_obj.order_by
                limit_expr = query_obj.limit_expr
                offset_expr = query_obj.offset_expr
            else:
                where_values = params.get("where")
                order_values = params.get("order_by")
                limit_expr = params.get("limit")
                offset_expr = params.get("offset")
            by_id_values = self._evaluate_expr_dict(params.get("by_id"), evaluator, step_name, "by id")
            filters: list[dict[str, Any]] = []
            used_primary = False
            if record.primary_key and record.primary_key in by_id_values:
                pk_field = record.fields.get(record.primary_key)
                if pk_field:
                    filters.append(
                        {
                            "field": record.primary_key,
                            "op": "eq",
                            "value": self._coerce_record_value(
                                record.name,
                                pk_field,
                                by_id_values[record.primary_key],
                                step_name,
                            ),
                        }
                    )
                    used_primary = True
            elif where_values:
                filters_tree = self._evaluate_where_conditions(where_values, evaluator, step_name, record)
            if used_primary:
                rows = list(frames.query(frame_name, filters))
            else:
                rows = list(frames.query(frame_name, None))
                if filters_tree:
                    rows = [row for row in rows if self._condition_tree_matches(filters_tree, row, alias or record.name)]
            if order_values:
                rows = self._sort_rows(rows, order_values, alias or record.name)
            offset_value = self._evaluate_pagination_expr(offset_expr, evaluator, step_name, f"offset {alias} by", default=0)
            if offset_value:
                rows = rows[offset_value:]
            limit_value = self._evaluate_pagination_expr(limit_expr, evaluator, step_name, f"limit {alias} to")
            if limit_value is not None:
                rows = rows[:limit_value]
            rows = [dict(row) for row in rows]
            if isinstance(query_obj, IRRecordQuery) and getattr(query_obj, "relationships", None):
                rows = self._apply_relationship_joins(
                    record,
                    rows,
                    query_obj.relationships,
                    runtime_ctx,
                )
            if used_primary:
                return rows[0] if rows else None
            return rows
        if kind == "db_update":
            by_id_values = self._evaluate_expr_dict(params.get("by_id"), evaluator, step_name, "by id")
            if not record.primary_key or record.primary_key not in by_id_values:
                raise Namel3ssError(
                    f"Step '{step_name}' must include primary key '{record.primary_key}' inside 'by id'."
                )
            pk_field = record.fields.get(record.primary_key)
            filters = [
                {
                    "field": record.primary_key,
                    "op": "eq",
                    "value": self._coerce_record_value(
                        record.name,
                        pk_field,
                        by_id_values[record.primary_key],
                        step_name,
                    ),
                }
            ]
            set_values = self._evaluate_expr_dict(params.get("set"), evaluator, step_name, "set")
            updates = self._prepare_record_values(
                record,
                set_values,
                step_name,
                include_defaults=False,
                enforce_required=False,
            )
            rows = frames.query(frame_name, filters)
            if not rows:
                return None
            existing_row = dict(rows[0])
            candidate_row = dict(existing_row)
            candidate_row.update(updates)
            self._validate_record_field_values(record, candidate_row)
            self._enforce_record_uniqueness(
                record,
                candidate_row,
                existing_row,
                frames,
                frame_name,
                operation="update",
            )
            self._enforce_record_foreign_keys(
                record,
                candidate_row,
                existing_row,
                frames,
                getattr(runtime_ctx, "records", None),
                operation="update",
            )
            for row in rows:
                row.update(updates)
            return dict(rows[0])
        if kind == "db_bulk_update":
            bulk_spec = params.get("bulk_update")
            if not isinstance(bulk_spec, IRBulkUpdateSpec):
                raise Namel3ssError("I need update many ... where: details to run this bulk update step.")
            set_entries = params.get("set")
            if not isinstance(set_entries, dict) or not set_entries:
                raise Namel3ssError(f"I need a 'set:' block inside update many {record.name.lower()}s to know which fields to change.")
            evaluated_updates = self._evaluate_expr_dict(set_entries, evaluator, step_name, "set")
            normalized_updates = self._prepare_record_values(
                record,
                evaluated_updates,
                step_name,
                include_defaults=False,
                enforce_required=False,
            )
            filters_tree = self._evaluate_where_conditions(bulk_spec.where_condition, evaluator, step_name, record)
            rows = list(frames.query(frame_name, None))
            if filters_tree:
                alias_label = bulk_spec.alias or record.name
                rows = [row for row in rows if self._condition_tree_matches(filters_tree, row, alias_label)]
            if not rows:
                return []
            runtime_records = getattr(runtime_ctx, "records", None)
            local_uniques: dict[tuple[str, Any | None], set[Any]] = {}
            staged_rows: list[tuple[dict[str, Any], dict[str, Any]]] = []
            for row in rows:
                existing_row = dict(row)
                candidate_row = dict(existing_row)
                candidate_row.update(normalized_updates)
                self._validate_record_field_values(record, candidate_row)
                self._enforce_record_uniqueness(
                    record,
                    candidate_row,
                    existing_row,
                    frames,
                    frame_name,
                    operation="update",
                )
                self._enforce_record_foreign_keys(
                    record,
                    candidate_row,
                    existing_row,
                    frames,
                    runtime_records,
                    operation="update",
                )
                self._track_pending_uniques(record, candidate_row, local_uniques)
                staged_rows.append((row, candidate_row))
            for row, _candidate in staged_rows:
                row.update(normalized_updates)
            return [dict(row) for row in rows]
        if kind == "db_delete":
            by_id_values = self._evaluate_expr_dict(params.get("by_id"), evaluator, step_name, "by id")
            if not record.primary_key or record.primary_key not in by_id_values:
                raise Namel3ssError(
                    f"Step '{step_name}' must include primary key '{record.primary_key}' inside 'by id'."
                )
            pk_field = record.fields.get(record.primary_key)
            filters = [
                {
                    "field": record.primary_key,
                    "op": "eq",
                    "value": self._coerce_record_value(
                        record.name,
                        pk_field,
                        by_id_values[record.primary_key],
                        step_name,
                    ),
                }
            ]
            deleted = frames.delete(frame_name, filters)
            return {"ok": deleted > 0, "deleted": deleted}
        if kind == "db_bulk_delete":
            bulk_spec = params.get("bulk_delete")
            if not isinstance(bulk_spec, IRBulkDeleteSpec):
                raise Namel3ssError("I need delete many ... where: details to run this bulk delete step.")
            filters_tree = self._evaluate_where_conditions(bulk_spec.where_condition, evaluator, step_name, record)
            if not filters_tree:
                raise Namel3ssError("delete many ... must include a 'where:' block to limit which records are removed.")
            deleted = frames.delete(frame_name, filters_tree)
            return {"ok": deleted > 0, "deleted": deleted}
        raise Namel3ssError(f"Unsupported record operation '{kind}'.")
