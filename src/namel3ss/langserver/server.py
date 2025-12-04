from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .. import ir, lexer, parser
from ..diagnostics import Diagnostic, create_diagnostic, legacy_to_structured
from ..diagnostics.pipeline import run_diagnostics
from ..diagnostics.runner import apply_strict_mode
from ..errors import Namel3ssError
from ..lang.formatter import format_source


TextDocumentSyncKind = 1  # Full text sync


@dataclass
class TextDocument:
    uri: str
    text: str
    version: int


class DocumentStore:
    def __init__(self) -> None:
        self._docs: dict[str, TextDocument] = {}

    def open(self, uri: str, text: str, version: int) -> None:
        self._docs[uri] = TextDocument(uri=uri, text=text, version=version)

    def update(self, uri: str, text: str, version: int) -> None:
        if uri in self._docs:
            self._docs[uri].text = text
            self._docs[uri].version = version
        else:
            self.open(uri, text, version)

    def close(self, uri: str) -> None:
        self._docs.pop(uri, None)

    def get(self, uri: str) -> Optional[TextDocument]:
        return self._docs.get(uri)


class LanguageServer:
    """
    Minimal LSP server that supports initialization, text sync, diagnostics, and formatting.
    """

    def __init__(self, *, strict: bool = False, output: Any = None) -> None:
        self.strict = strict
        self.docs = DocumentStore()
        self.shutdown_requested = False
        self.initialized = False
        self._out = output or sys.stdout.buffer
        self.sent_notifications: list[dict[str, Any]] = []

    # --- JSON-RPC helpers -------------------------------------------------
    def _write_message(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False)
        message = f"Content-Length: {len(body.encode('utf-8'))}\r\n\r\n{body}"
        self._out.write(message.encode("utf-8"))
        self._out.flush()

    def send_response(self, request_id: Any, result: Any) -> None:
        response = {"jsonrpc": "2.0", "id": request_id, "result": result}
        self._write_message(response)

    def send_error(self, request_id: Any, code: int, message: str) -> None:
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        }
        self._write_message(response)

    def send_notification(self, method: str, params: dict[str, Any]) -> None:
        payload = {"jsonrpc": "2.0", "method": method, "params": params}
        self.sent_notifications.append(payload)
        self._write_message(payload)

    # --- Core LSP lifecycle ----------------------------------------------
    def handle_request(self, request: dict[str, Any]) -> Optional[dict[str, Any]]:
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")

        if method == "initialize":
            capabilities = {
                "capabilities": {
                    "textDocumentSync": {
                        "openClose": True,
                        "change": TextDocumentSyncKind,
                    },
                    "documentFormattingProvider": True,
                },
                "serverInfo": {"name": "Namel3ss LSP", "version": "1.0"},
            }
            self.initialized = True
            if request_id is not None:
                return {"jsonrpc": "2.0", "id": request_id, "result": capabilities}
            return None

        if method == "initialized":
            return None

        if method == "shutdown":
            self.shutdown_requested = True
            return {"jsonrpc": "2.0", "id": request_id, "result": None}

        if method == "exit":
            sys.exit(0)

        if method == "textDocument/didOpen":
            self._handle_did_open(params)
            return None

        if method == "textDocument/didChange":
            self._handle_did_change(params)
            return None

        if method == "textDocument/didClose":
            self._handle_did_close(params)
            return None

        if method == "textDocument/formatting":
            edits = self._handle_formatting(params)
            if request_id is not None:
                return {"jsonrpc": "2.0", "id": request_id, "result": edits}
            return None

        # Unknown method
        if request_id is not None:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "Method not found"}}
        return None

    # --- Handlers ---------------------------------------------------------
    def _handle_did_open(self, params: dict[str, Any]) -> None:
        text_doc = params.get("textDocument", {})
        uri = text_doc.get("uri")
        text = text_doc.get("text", "")
        version = text_doc.get("version", 0)
        if not uri:
            return
        self.docs.open(uri, text, version)
        self._publish_diagnostics(uri, text)

    def _handle_did_change(self, params: dict[str, Any]) -> None:
        text_doc = params.get("textDocument", {})
        uri = text_doc.get("uri")
        version = text_doc.get("version", 0)
        changes = params.get("contentChanges", [])
        if not uri or not changes:
            return
        # Full text sync
        text = changes[-1].get("text", "")
        self.docs.update(uri, text, version)
        self._publish_diagnostics(uri, text)

    def _handle_did_close(self, params: dict[str, Any]) -> None:
        text_doc = params.get("textDocument", {})
        uri = text_doc.get("uri")
        if not uri:
            return
        self.docs.close(uri)
        # Clear diagnostics on close
        self.send_notification(
            "textDocument/publishDiagnostics",
            {"uri": uri, "diagnostics": []},
        )

    def _handle_formatting(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        text_doc = params.get("textDocument", {})
        uri = text_doc.get("uri")
        if not uri:
            return []
        doc = self.docs.get(uri)
        if not doc:
            return []
        formatted = format_source(doc.text, filename=uri)
        if formatted == doc.text:
            return []
        lines = doc.text.splitlines(keepends=True)
        end_line = len(lines)
        end_char = len(lines[-1]) - (1 if lines and lines[-1].endswith("\n") else 0) if lines else 0
        return [
            {
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": end_line, "character": end_char},
                },
                "newText": formatted,
            }
        ]

    # --- Diagnostics helpers ---------------------------------------------
    def _publish_diagnostics(self, uri: str, text: str) -> None:
        diags = self._diagnose_text(uri, text)
        lsp_diags = [self._to_lsp_diag(d) for d in diags]
        self.send_notification(
            "textDocument/publishDiagnostics",
            {"uri": uri, "diagnostics": lsp_diags},
        )

    def _diagnose_text(self, uri: str, text: str) -> List[Diagnostic]:
        diag_list: list[Diagnostic] = []
        try:
            tokens = lexer.Lexer(text, filename=uri).tokenize()
            module = parser.Parser(tokens).parse_module()
        except Namel3ssError as err:
            diag = create_diagnostic(
                "N3-0001",
                message_kwargs={"detail": err.message},
                file=uri,
                line=err.line,
                column=err.column,
            )
            diag_list.append(diag)
            return diag_list
        try:
            program = ir.ast_to_ir(module)
        except Namel3ssError as err:
            code = "N3-1005"
            kwargs = {"field": "program", "kind": "module"}
            if "Duplicate" in err.message:
                code = "N3-1004"
                kwargs = {"name": err.message, "scope": "module"}
            diag = create_diagnostic(
                code,
                message_kwargs=kwargs,
                file=uri,
                line=err.line,
                column=err.column,
                hint=err.message,
            )
            diag_list.append(diag)
            return diag_list

        legacy_diags = run_diagnostics(program, available_plugins=set())
        structured_diags = [legacy_to_structured(d) for d in legacy_diags]
        diag_list.extend(structured_diags)
        diag_list, _ = apply_strict_mode(diag_list, self.strict)
        return diag_list

    @staticmethod
    def _to_lsp_diag(diag: Diagnostic) -> dict[str, Any]:
        severity_map = {"error": 1, "warning": 2, "info": 3}
        start_line = max((diag.line or 1) - 1, 0)
        start_char = max((diag.column or 1) - 1, 0)
        return {
            "range": {
                "start": {"line": start_line, "character": start_char},
                "end": {"line": start_line, "character": start_char + 1},
            },
            "severity": severity_map.get(diag.severity, 3),
            "code": diag.code,
            "source": "namel3ss",
            "message": diag.message,
        }

    # --- IO loop ----------------------------------------------------------
    def run_stdio(self) -> None:
        """
        Blocking stdio loop implementing the LSP header framing protocol.
        """
        stdin = sys.stdin.buffer
        while not self.shutdown_requested:
            headers = {}
            while True:
                line = stdin.readline()
                if not line:
                    return
                line = line.decode("utf-8").strip()
                if not line:
                    break
                if ":" in line:
                    key, value = line.split(":", 1)
                    headers[key.strip().lower()] = value.strip()
            content_length = int(headers.get("content-length", "0"))
            if content_length == 0:
                continue
            body = stdin.read(content_length)
            if not body:
                continue
            request = json.loads(body.decode("utf-8"))
            response = self.handle_request(request)
            if response:
                self._write_message(response)

