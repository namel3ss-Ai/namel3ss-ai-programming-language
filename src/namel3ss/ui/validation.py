"""
Form validation utilities.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Tuple


def validate_form(fields: list[dict[str, Any]], payload: dict[str, Any]) -> Tuple[bool, Dict[str, str]]:
    errors: Dict[str, str] = {}
    for field in fields:
        fid = field.get("id") or field.get("name")
        if not fid:
            continue
        value = payload.get(fid)
        if field.get("required") and (value is None or value == ""):
            errors[fid] = "required"
            continue
        ftype = (field.get("type") or "string").lower()
        if value is None:
            continue
        if ftype == "number":
            try:
                num = float(value)
                if "min" in field and num < field["min"]:
                    errors[fid] = "min"
                if "max" in field and num > field["max"]:
                    errors[fid] = "max"
            except (TypeError, ValueError):
                errors[fid] = "type"
        if ftype == "string":
            if "min_length" in field and len(str(value)) < field["min_length"]:
                errors[fid] = "min_length"
            if "max_length" in field and len(str(value)) > field["max_length"]:
                errors[fid] = "max_length"
        regex = field.get("regex")
        if regex and not re.match(regex, str(value)):
            errors[fid] = "regex"
    return (len(errors) == 0), errors
