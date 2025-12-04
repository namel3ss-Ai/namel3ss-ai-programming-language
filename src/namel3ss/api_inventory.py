"""
Internal helpers to inventory CLI commands and HTTP routes.
Used by tests to keep the public surface stable for RC.
"""

from __future__ import annotations

from typing import Iterable, List, Tuple

from fastapi import FastAPI


def list_cli_commands() -> List[str]:
    """
    Return the list of top-level n3 CLI commands.
    Uses the shared parser builder from cli.py to avoid drift.
    """
    from .cli import build_cli_parser

    parser = build_cli_parser()
    commands = getattr(parser, "_n3_commands", [])
    return sorted(commands)


def list_http_routes(app: FastAPI) -> List[Tuple[str, str]]:
    """
    Enumerate HTTP routes as (METHOD, path) pairs, excluding implicit HEAD/OPTIONS.
    """
    routes: list[tuple[str, str]] = []
    for route in app.routes:
        if not hasattr(route, "methods"):
            continue
        methods: Iterable[str] = route.methods or []
        for method in methods:
            if method in {"HEAD", "OPTIONS"}:
                continue
            routes.append((method.upper(), route.path))
    return sorted(routes)
