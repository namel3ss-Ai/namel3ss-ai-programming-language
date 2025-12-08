from namel3ss import parser, ir
from namel3ss.ui.manifest import build_ui_manifest


def _first_button(manifest):
    first_page = manifest["pages"][0]
    # find first button in layout
    for el in first_page["layout"]:
        if el["type"] == "section":
            for child in el["layout"]:
                if child["type"] == "button":
                    return child
    return None


def test_manifest_includes_navigate_path():
    mod = parser.parse_source(
        '''
page is "home" at "/":
  section is "main":
    button is "Go":
      on click:
        navigate to "/chat"

page is "chat" at "/chat":
  section is "main":
    text is "Chat"
'''
    )
    program = ir.ast_to_ir(mod)
    manifest = build_ui_manifest(program)
    btn = _first_button(manifest)
    assert btn is not None
    assert btn.get("onClick") is not None
    assert btn["onClick"]["kind"] == "navigate"
    target = btn["onClick"]["target"]
    assert target["path"] == "/chat"
    assert target["pageName"] is None


def test_manifest_includes_navigate_page():
    mod = parser.parse_source(
        '''
page is "home" at "/":
  section is "main":
    button is "Go":
      on click:
        navigate to page is "chat"

page is "chat" at "/chat":
  section is "main":
    text is "Chat"
'''
    )
    program = ir.ast_to_ir(mod)
    manifest = build_ui_manifest(program)
    btn = _first_button(manifest)
    assert btn is not None
    assert btn.get("onClick") is not None
    assert btn["onClick"]["kind"] == "navigate"
    target = btn["onClick"]["target"]
    assert target["pageName"] == "chat"
    assert target["path"] == "/chat"
