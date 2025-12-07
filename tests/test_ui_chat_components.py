from textwrap import dedent

from namel3ss.lexer import Lexer
from namel3ss.parser import Parser
from namel3ss.ir import ast_to_ir
from namel3ss.ui.manifest import build_ui_manifest
from namel3ss.ui.runtime import render_layout, UIStateStore


def test_parse_message_list_and_messages():
    code = dedent(
        """
        page is "chat" at "/chat":
          section is "main":
            message_list:
              message:
                role is "user"
                text is state.question

              message is "answer":
                role is "assistant"
                text is state.answer
        """
    )
    module = Parser(Lexer(code).tokenize()).parse_module()
    msg_list = module.declarations[0].layout[0].layout[0]
    assert msg_list.__class__.__name__ == "MessageListNode"
    assert len(msg_list.children) == 2
    first, second = msg_list.children
    assert first.role is not None and second.role is not None
    assert second.name == "answer"
    assert second.text_expr is not None


def test_manifest_contains_message_list():
    code = dedent(
        """
        page "chat" at "/chat":
          section "main":
            message_list:
              message:
                role "user"
                text "Hello"
        """
    )
    program = ast_to_ir(Parser(Lexer(code).tokenize()).parse_module())
    data = build_ui_manifest(program)
    layout = data["pages"][0]["layout"][0]["layout"]
    msg_list = next(el for el in layout if el["type"] == "message_list")
    assert msg_list["layout"][0]["type"] == "message"
    assert msg_list["layout"][0]["role"] in (None, "user")


def test_runtime_renders_messages():
    code = dedent(
        """
        page is "chat" at "/chat":
          state question is "Hi"
          state answer is "Hello back"
          section is "main":
            message_list:
              message:
                role is "user"
                text is state.question
              message:
                role is "assistant"
                text is state.answer
        """
    )
    ir = ast_to_ir(Parser(Lexer(code).tokenize()).parse_module())
    page = next(iter(ir.pages.values()))
    rendered = render_layout(page.layout, UIStateStore({"question": "Hi", "answer": "Hello back"}))

    def find_message_list(nodes):
        for el in nodes:
            if el.get("type") == "message_list":
                return el
            if "layout" in el:
                found = find_message_list(el["layout"])
                if found:
                    return found
        return None

    msg_list = find_message_list(rendered)
    assert msg_list is not None
    assert len(msg_list["layout"]) == 2
    user_msg = msg_list["layout"][0]
    assert user_msg["role"] == "user" or user_msg["role"] is None
    assert user_msg["text"] == "Hi"
