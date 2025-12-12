from __future__ import annotations

import json
import re
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from ....errors import Namel3ssError
from ...graph import FlowRuntimeContext

__all__ = ["FlowEngineRecordHelpersMixin"]


class FlowEngineRecordHelpersMixin:
    def _resolve_record_default_value(self, record_name: str, field, step_name: str) -> Any:
        default_value = getattr(field, "default", None)
        if default_value is None:
            return None
        if default_value == "now":
            if getattr(field, "type", None) != "datetime":
                raise Namel3ssError(
                    f"I can't use this default for field {field.name} on record {record_name} because it doesn't match the field type."
                )
            raw_value = datetime.utcnow()
        else:
            raw_value = default_value
        try:
            return self._coerce_record_value(record_name, field, raw_value, step_name)
        except Namel3ssError:
            raise Namel3ssError(
                f"I can't use this default for field {field.name} on record {record_name} because it doesn't match the field type."
            )

    def _coerce_record_value(self, record_name: str, field, value: Any, step_name: str) -> Any:
        if value is None:
            return None
        ftype = getattr(field, "type", "string")
        try:
            if ftype in {"string", "text"}:
                return "" if value is None else str(value)
            if ftype == "int":
                if isinstance(value, bool):
                    return int(value)
                if isinstance(value, (int, float)):
                    if isinstance(value, float) and not value.is_integer():
                        raise ValueError("cannot truncate non-integer float")
                    return int(value)
                return int(str(value))
            if ftype == "float":
                if isinstance(value, bool):
                    return float(int(value))
                if isinstance(value, (int, float)):
                    return float(value)
                return float(str(value))
            if ftype == "bool":
                if isinstance(value, bool):
                    return value
                if isinstance(value, str):
                    normalized = value.strip().lower()
                    if normalized in {"true", "false"}:
                        return normalized == "true"
                raise ValueError("expected boolean literal")
            if ftype == "uuid":
                text = str(value)
                try:
                    UUID(text)
                except Exception:
                    # Treat any stringable value as acceptable; upstream validation is lenient.
                    return text
                return text
            if ftype == "datetime":
                if isinstance(value, datetime):
                    return value
                if isinstance(value, str):
                    return datetime.fromisoformat(value)
                raise ValueError("expected datetime or ISO-8601 string")
            if ftype == "decimal":
                if isinstance(value, Decimal):
                    return value
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    return Decimal(str(value))
                if isinstance(value, str):
                    return Decimal(value)
                raise ValueError("expected decimal-compatible value")
            if ftype == "array":
                if isinstance(value, list):
                    return value
                if isinstance(value, tuple):
                    return list(value)
                if isinstance(value, str):
                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        return parsed
                    raise ValueError("expected JSON array string")
                raise ValueError("expected list or array-like value")
            if ftype == "json":
                if isinstance(value, (dict, list)):
                    return value
                if isinstance(value, str):
                    parsed = json.loads(value)
                    if isinstance(parsed, (dict, list)):
                        return parsed
                    raise ValueError("expected JSON object or array string")
                raise ValueError("expected JSON object or array value")
        except Exception as exc:
            raise Namel3ssError(
                f"Field '{field.name}' on record '{record_name}' could not be coerced to type '{ftype}': {exc}"
            ) from exc
        return value

    def _prepare_record_values(
        self,
        record,
        values: dict[str, Any],
        step_name: str,
        include_defaults: bool,
        enforce_required: bool,
    ) -> dict[str, Any]:
        normalized: dict[str, Any] = {}
        for key, raw in values.items():
            field = record.fields.get(key)
            if not field:
                raise Namel3ssError(
                    f"Record '{record.name}' has no field named '{key}' (step '{step_name}')."
                )
            coerced = self._coerce_record_value(record.name, field, raw, step_name)
            if coerced is None and enforce_required and (field.required or field.primary_key):
                raise Namel3ssError(f"N3L-1502: I can't create a {record.name} record because required field {key} is missing.")
            normalized[key] = coerced
        if include_defaults:
            for key, field in record.fields.items():
                if key in normalized:
                    continue
                if field.default is not None:
                    normalized[key] = self._resolve_record_default_value(record.name, field, step_name)
                elif enforce_required and field.required:
                    raise Namel3ssError(f"N3L-1502: I can't create a {record.name} record because required field {key} is missing.")
        if enforce_required:
            for key, field in record.fields.items():
                if (field.required or field.primary_key) and normalized.get(key) is None:
                    raise Namel3ssError(f"N3L-1502: I can't create a {record.name} record because required field {key} is missing.")
        return normalized

    def _format_unique_violation_error(
        self,
        record_name: str,
        field_name: str,
        value: Any,
        scope_label: str | None,
    ) -> str:
        value_display = f"\"{value}\"" if isinstance(value, str) else str(value)
        record_lower = record_name.lower()
        if scope_label:
            return (
                f'I can’t save this {record_name} because {field_name} {value_display} is already used inside this {scope_label}.\n'
                f"Each {record_lower} must have a unique {field_name} within {scope_label.lower()}."
            )
        return (
            f'I can’t save this {record_name} because {field_name} {value_display} is already used.\n'
            f"Each {record_lower} must have a unique {field_name}."
        )

    def _format_missing_scope_value_error(
        self,
        record_name: str,
        field_name: str,
        scope_label: str,
        scope_field: str,
    ) -> str:
        return (
            f'I can’t enforce must be unique within "{scope_label}" on {record_name}.{field_name} because I can’t find a value for {scope_field} on this record.\n'
            f"Provide {scope_field} before saving or remove that uniqueness rule."
        )

    def _format_foreign_key_violation_error(
        self,
        record_name: str,
        field_name: str,
        value: Any,
        target_record: str,
    ) -> str:
        value_display = f"\"{value}\"" if isinstance(value, str) else str(value)
        return (
            f'I can’t save this {record_name} because {field_name} {value_display} does not point to an existing {target_record}.\n'
            f"Make sure you use a valid {target_record} id here."
        )

    def _enforce_record_uniqueness(
        self,
        record,
        candidate_row: dict[str, Any],
        existing_row: dict[str, Any] | None,
        frames,
        frame_name: str,
        operation: str,
    ) -> None:
        pk_name = getattr(record, "primary_key", None)
        pk_value = None
        if pk_name:
            if operation == "update" and existing_row is not None:
                pk_value = existing_row.get(pk_name)
            else:
                pk_value = candidate_row.get(pk_name)
        for field in record.fields.values():
            if not getattr(field, "is_unique", False):
                continue
            new_value = candidate_row.get(field.name)
            if new_value is None:
                continue
            scope_label = getattr(field, "unique_scope", None)
            scope_field = getattr(field, "unique_scope_field", None)
            scope_value = None
            if scope_label:
                if not scope_field:
                    raise Namel3ssError(
                        f'I can’t enforce must be unique within "{scope_label}" on {record.name}.{field.name} because I can’t resolve the scope field.'
                    )
                scope_value = candidate_row.get(scope_field)
                if scope_value is None:
                    raise Namel3ssError(
                        self._format_missing_scope_value_error(record.name, field.name, scope_label, scope_field)
                    )
            if existing_row is not None:
                previous_value = existing_row.get(field.name)
                scope_changed = False
                if scope_field:
                    previous_scope = existing_row.get(scope_field)
                    scope_changed = previous_scope != scope_value
                if previous_value == new_value and not scope_changed:
                    continue
            filters = [{"field": field.name, "op": "eq", "value": new_value}]
            if scope_field:
                filters.append({"field": scope_field, "op": "eq", "value": scope_value})
            matches = frames.query(frame_name, filters)
            for row in matches:
                if operation == "update" and pk_name and row.get(pk_name) == pk_value:
                    continue
                raise Namel3ssError(
                    self._format_unique_violation_error(record.name, field.name, new_value, scope_label)
                )

    def _enforce_record_foreign_keys(
        self,
        record,
        candidate_row: dict[str, Any],
        existing_row: dict[str, Any] | None,
        frames,
        runtime_records: dict[str, Any] | None,
        operation: str,
    ) -> None:
        if not runtime_records:
            runtime_records = {}
        for field in record.fields.values():
            target_record_name = getattr(field, "references_record", None)
            target_field_name = getattr(field, "reference_target_field", None)
            if not target_record_name or not target_field_name:
                continue
            new_value = candidate_row.get(field.name)
            if new_value is None:
                continue
            if existing_row is not None:
                previous_value = existing_row.get(field.name)
                if previous_value == new_value:
                    continue
            target_record = runtime_records.get(target_record_name)
            if not target_record:
                raise Namel3ssError(
                    f'I can’t enforce references "{target_record_name}" on {record.name}.{field.name} because record "{target_record_name}" is not available at runtime.'
                )
            target_frame = getattr(target_record, "frame", None)
            if not target_frame:
                raise Namel3ssError(
                    f'I can’t enforce references "{target_record_name}" on {record.name}.{field.name} because the referenced record has no frame.'
                )
            filters = [
                {
                    "field": target_field_name,
                    "op": "eq",
                    "value": new_value,
                }
            ]
            matches = frames.query(target_frame, filters)
            if not matches:
                raise Namel3ssError(
                    self._format_foreign_key_violation_error(record.name, field.name, new_value, target_record_name)
                )

    def _validate_record_field_values(
        self,
        record,
        candidate_row: dict[str, Any],
    ) -> None:
        for field in record.fields.values():
            value = candidate_row.get(field.name)
            self._validate_single_field_value(record, field, value)

    def _validate_single_field_value(self, record, field, value: Any) -> None:
        if value is None:
            return
        enum_values = getattr(field, "enum_values", None)
        if enum_values:
            if value not in enum_values:
                allowed_label = "[" + ", ".join(self._format_validation_value(val) for val in enum_values) + "]"
                raise Namel3ssError(
                    self._format_validation_error(
                        record.name,
                        f"{field.name} must be one of {allowed_label} but got {self._format_validation_value(value)}.",
                    )
                )
        numeric_min = getattr(field, "numeric_min", None)
        if numeric_min is not None and value < numeric_min:
            raise Namel3ssError(
                self._format_validation_error(
                    record.name,
                    f"{field.name} must be at least {self._format_validation_value(numeric_min)} but got {self._format_validation_value(value)}.",
                )
            )
        numeric_max = getattr(field, "numeric_max", None)
        if numeric_max is not None and value > numeric_max:
            raise Namel3ssError(
                self._format_validation_error(
                    record.name,
                    f"{field.name} must be at most {self._format_validation_value(numeric_max)} but got {self._format_validation_value(value)}.",
                )
            )
        length_min = getattr(field, "length_min", None)
        length_max = getattr(field, "length_max", None)
        if length_min is not None or length_max is not None:
            unit = "items"
            if isinstance(value, str):
                current_length = len(value)
                unit = "characters"
            elif isinstance(value, (list, tuple)):
                current_length = len(value)
            else:
                current_length = None
            if current_length is not None:
                if length_min is not None and current_length < length_min:
                    raise Namel3ssError(
                        self._format_validation_error(
                            record.name,
                            f"{field.name} must have length at least {length_min} {unit} but got {current_length}.",
                        )
                    )
                if length_max is not None and current_length > length_max:
                    raise Namel3ssError(
                        self._format_validation_error(
                            record.name,
                            f"{field.name} must have length at most {length_max} {unit} but got {current_length}.",
                        )
                    )
        pattern = getattr(field, "pattern", None)
        if pattern:
            if not isinstance(value, str):
                raise Namel3ssError(
                    self._format_validation_error(
                        record.name,
                        f"{field.name} must match pattern \"{pattern}\" but got {self._format_validation_value(value)}.",
                    )
                )
            if not re.fullmatch(pattern, value):
                raise Namel3ssError(
                    self._format_validation_error(
                        record.name,
                        f"{field.name} must match pattern \"{pattern}\" but got {self._format_validation_value(value)}.",
                    )
                )

    def _format_validation_error(self, record_name: str, message: str) -> str:
        return f"I can't save this {record_name} because {message}"

    def _format_validation_value(self, value: Any) -> str:
        if isinstance(value, str):
            return f'"{value}"'
        return str(value)

    def _track_pending_uniques(
        self,
        record,
        candidate_row: dict[str, Any],
        tracker: dict[tuple[str, Any | None], set[Any]],
    ) -> None:
        for field in record.fields.values():
            if not getattr(field, "is_unique", False):
                continue
            value = candidate_row.get(field.name)
            if value is None:
                continue
            scope_field = getattr(field, "unique_scope_field", None)
            scope_label = getattr(field, "unique_scope", None)
            scope_value = candidate_row.get(scope_field) if scope_field else None
            if scope_field and scope_value is None:
                continue
            key = (field.name, scope_value if scope_field else None)
            seen = tracker.setdefault(key, set())
            if value in seen:
                raise Namel3ssError(
                    self._format_unique_violation_error(record.name, field.name, value, scope_label)
                )
            seen.add(value)

    def _apply_relationship_joins(
        self,
        record,
        rows: list[dict[str, Any]],
        relationships: list,
        runtime_ctx: FlowRuntimeContext,
    ) -> list[dict[str, Any]]:
        if not rows or not relationships:
            return rows
        frames = runtime_ctx.frames
        if frames is None:
            raise Namel3ssError("Frame registry unavailable for relationship queries.")
        runtime_records = getattr(runtime_ctx, "records", {}) or {}
        for join in relationships:
            target_record_name = getattr(join, "target_record", None)
            target_field = getattr(join, "target_field", None)
            attachment_field = getattr(join, "attachment_field", None) or join.related_alias
            via_field = join.via_field
            if not target_record_name or not target_field:
                raise Namel3ssError(
                    f"I can’t load related records for '{attachment_field}' because the relationship metadata is incomplete."
                )
            target_record = runtime_records.get(target_record_name)
            if not target_record:
                raise Namel3ssError(
                    f'I can’t load related {target_record_name} records because "{target_record_name}" is not registered at runtime.'
                )
            target_frame = getattr(target_record, "frame", None)
            if not target_frame:
                raise Namel3ssError(
                    f'I can’t load related {target_record_name} records because "{target_record_name}" is missing a frame binding.'
                )
            fk_values = {row.get(via_field) for row in rows if row.get(via_field) is not None}
            related_map: dict[Any, dict[str, Any]] = {}
            if fk_values:
                filters = [{"field": target_field, "op": "in", "value": list(fk_values)}]
                related_rows = frames.query(target_frame, filters)
                for rel_row in related_rows:
                    rel_dict = dict(rel_row)
                    key = rel_dict.get(target_field)
                    if key is not None:
                        related_map[key] = rel_dict
            for row in rows:
                fk_value = row.get(via_field)
                if fk_value is None:
                    row[attachment_field] = None
                else:
                    row[attachment_field] = related_map.get(fk_value)
        return rows
