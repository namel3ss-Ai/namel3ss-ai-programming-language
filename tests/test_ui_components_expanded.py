from textwrap import dedent
from pathlib import Path

from namel3ss.lexer import Lexer
from namel3ss.parser import Parser
from namel3ss.ir import ast_to_ir
from namel3ss.ui.runtime import render_layout, UIStateStore


def test_parse_expanded_components():
    code = dedent(
        '''
        page is "chat" at "/chat":
          section is "main":
            card is "conversation":
              row:
                text is "User:"
                badge is "Premium"
              textarea is "question":
                bind is question
              column:
                text is "Footer"
        '''
    )
    module = Parser(Lexer(code).tokenize()).parse_module()
    page = module.declarations[0]
    layout = page.layout[0].layout
    assert layout and layout[0].__class__.__name__ == "CardNode"
    card = layout[0]
    assert card.title == "conversation"
    assert card.children[0].__class__.__name__ == "RowNode"
    row = card.children[0]
    assert row.children[-1].__class__.__name__ == "BadgeNode"
    column = card.children[-1]
    assert column.__class__.__name__ == "ColumnNode"
    textarea = card.children[1]
    assert textarea.__class__.__name__ == "TextareaNode"
    assert textarea.var_name == "question"


def test_manifest_includes_expanded_components(tmp_path: Path):
    code = dedent(
        '''\
        page is "home" at "/":
          section is "main":
            card is "conversation":
              row:
                text is "User:"
                badge is "Premium"
              textarea is "question":
                bind is question
              column:
                text is "Footer"
        '''
    )
    program = ast_to_ir(Parser(Lexer(code).tokenize()).parse_module())
    from namel3ss.ui.manifest import build_ui_manifest

    data = build_ui_manifest(program)
    layout = data["pages"][0]["layout"][0]["layout"]
    card = next(el for el in layout if el["type"] == "card")
    assert card["title"] == "conversation"
    row = next(el for el in card["layout"] if el["type"] == "row")
    badge = next(el for el in row["layout"] if el["type"] == "badge")
    assert badge["text"] == "Premium"
    textarea = next(el for el in card["layout"] if el["type"] == "textarea")
    assert textarea["label"] == "question"


def test_runtime_render_textarea_binding():
    code = dedent(
        '''
        page is "chat" at "/chat":
          state question is "hello"
          section is "main":
            textarea is "question":
              bind is question
        '''
    )
    ir = ast_to_ir(Parser(Lexer(code).tokenize()).parse_module())
    page = next(iter(ir.pages.values()))
    state = UIStateStore({"question": "hello"})
    rendered = render_layout(page.layout, state)
    def find_textarea(nodes):
        for el in nodes:
            if el.get("type") == "textarea":
                return el
            if "layout" in el:
                found = find_textarea(el["layout"])
                if found:
                    return found
        return None

    textarea = find_textarea(rendered)
    assert textarea is not None
    assert textarea["value"] == "hello"
