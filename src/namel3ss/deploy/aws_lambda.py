"""
AWS Lambda adapter for Namel3ss FastAPI app.
"""

from __future__ import annotations

import asyncio
import base64
from typing import Any, Dict

from namel3ss.server import create_app


app = create_app()


async def _invoke_asgi(method: str, path: str, headers: Dict[str, str], body: bytes) -> Dict[str, Any]:
    loop = asyncio.get_running_loop()
    response: Dict[str, Any] = {"status": 500, "headers": [], "body": b""}

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        if message["type"] == "http.response.start":
            response["status"] = message["status"]
            response["headers"] = message.get("headers", [])
        elif message["type"] == "http.response.body":
            response["body"] += message.get("body", b"")

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "path": path,
        "raw_path": path.encode(),
        "headers": [(k.encode("latin-1"), v.encode("latin-1")) for k, v in headers.items()],
        "query_string": b"",
        "server": ("lambda", 80),
        "client": ("lambda", 0),
    }
    await app(scope, receive, send)
    return response


def lambda_handler(event, context) -> Dict[str, Any]:
    method = event.get("httpMethod", "GET")
    path = event.get("path", "/")
    headers = {k: v for k, v in (event.get("headers") or {}).items()}
    body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        body_bytes = base64.b64decode(body)
    else:
        body_bytes = body.encode()
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_invoke_asgi(method, path, headers, body_bytes))
    finally:
        asyncio.set_event_loop(None)
        loop.close()
    return {
        "statusCode": result["status"],
        "headers": {k.decode(): v.decode() for k, v in result.get("headers", [])},
        "body": result["body"].decode(),
        "isBase64Encoded": False,
    }
