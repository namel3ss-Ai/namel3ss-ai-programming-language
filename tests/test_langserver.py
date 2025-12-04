from __future__ import annotations

from unittest import mock
import io

from namel3ss.cli import build_cli_parser, main
from namel3ss.lang.formatter import format_source
from namel3ss.langserver import LanguageServer


def apply_edits(text: str, edits: list[dict]) -> str:
    if not edits:
        return text
    # Only full document replace is used
    return edits[-1]["newText"]


def test_initialize_capabilities():
    server = LanguageServer(output=io.BytesIO())
    resp = server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert resp is not None
    caps = resp["result"]["capabilities"]
    assert caps["documentFormattingProvider"] is True
    assert caps["textDocumentSync"]["openClose"] is True


def test_did_open_and_diagnostics_clean():
    server = LanguageServer(output=io.BytesIO())
    doc = (
        'app "hello":\n'
        '  entry_page "home"\n\n'
        'page "home":\n'
        '  route "/"\n'
        '  section "hero":\n'
        '    component "text":\n'
        '      value "Welcome to Namel3ss"\n'
        '    component "form":\n'
        '      value "Enter your name"\n'
    )
    server.handle_request(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": "file:///test.ai", "text": doc, "version": 1}},
        }
    )
    assert server.sent_notifications
    publish = server.sent_notifications[-1]
    assert publish["method"] == "textDocument/publishDiagnostics"
    assert publish["params"]["diagnostics"] == []


def test_diagnostics_on_invalid_source():
    server = LanguageServer(output=io.BytesIO())
    bad_doc = "app broken {\n  page home {\n    title = \"oops\"\n"  # missing closing
    server.handle_request(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": "file:///bad.ai", "text": bad_doc, "version": 1}},
        }
    )
    publish = server.sent_notifications[-1]
    diags = publish["params"]["diagnostics"]
    assert diags
    assert diags[0]["code"] == "N3-0001"
    assert diags[0]["severity"] == 1


def test_formatting_returns_full_document_edit_and_idempotent():
    server = LanguageServer(output=io.BytesIO())
    ugly = (
        'app "foo":\n'
        '  entry_page "home"\n'
        "\n"
        'page "home":\n'
        '  route "/"  \n'
    )
    server.handle_request(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": "file:///fmt.ai", "text": ugly, "version": 1}},
        }
    )
    edits = server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "textDocument/formatting",
            "params": {"textDocument": {"uri": "file:///fmt.ai"}},
        }
    )["result"]
    formatted = apply_edits(ugly, edits)
    assert formatted == format_source(ugly, filename="file:///fmt.ai")
    # apply edits back to doc store to test idempotence
    server.docs.update("file:///fmt.ai", formatted, version=2)
    edits_again = server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "textDocument/formatting",
            "params": {"textDocument": {"uri": "file:///fmt.ai"}},
        }
    )["result"]
    assert edits_again == []


def test_did_change_updates_diagnostics():
    server = LanguageServer(output=io.BytesIO())
    doc = "app foo { page home { title = \"Ok\" } }\n"
    server.handle_request(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": "file:///change.ai", "text": doc, "version": 1}},
        }
    )
    broken = "app foo {\n  page home { title = \"Ok\"\n"
    server.handle_request(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didChange",
            "params": {
                "textDocument": {"uri": "file:///change.ai", "version": 2},
                "contentChanges": [{"text": broken}],
            },
        }
    )
    publish = server.sent_notifications[-1]
    assert publish["params"]["diagnostics"]
    assert publish["params"]["diagnostics"][0]["severity"] == 1


def test_cli_lsp_invokes_server_run():
    parser = build_cli_parser()
    with mock.patch("namel3ss.langserver.LanguageServer.run_stdio") as run:
        main(["lsp"])
        run.assert_called_once()
