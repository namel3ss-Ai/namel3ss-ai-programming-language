from __future__ import annotations

import datetime
import json
import math
import urllib.request
from typing import Any

from namel3ss.plugins.sdk import PluginSDK


def http_get(url: str) -> str:
    with urllib.request.urlopen(url) as resp:  # nosec - simple utility, caller controlled in dev
        return resp.read().decode("utf-8", errors="ignore")


def get_time() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def math_eval(expression: str) -> Any:
    allowed = {"__builtins__": {}}
    # allow only digits, operators, and whitespace
    cleaned = expression.strip()
    if not cleaned or any(ch not in "0123456789+-*/(). %e" for ch in cleaned):
        raise ValueError("Expression contains unsupported characters")
    return eval(cleaned, allowed, {})


def register_tools(sdk: PluginSDK) -> None:
    sdk.tools.register_tool("http_get", http_get, "HTTP GET utility")
    sdk.tools.register_tool("get_time", get_time, "Current UTC time")
    sdk.tools.register_tool("math_eval", math_eval, "Evaluate simple math expression")
