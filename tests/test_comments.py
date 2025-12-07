from textwrap import dedent

from namel3ss import parser
from namel3ss.ast_nodes import FlowDecl, PageDecl


def test_comments_standalone_and_inline():
    code = dedent(
        '''
        # top-level comment
        app "Test":
          entry_page "home"

        page is "home" at "/":
          # comment inside page
          section is "main":
            text is "Hello"  # inline comment on text

        # comment between decls
        flow is "chat":  # main chatbot flow
          step is "answer":  # answer step
            kind is "ai"  # ai step
            target is "support_bot"  # target
        '''
    )
    module = parser.parse_source(code)
    pages = [d for d in module.declarations if isinstance(d, PageDecl)]
    flows = [d for d in module.declarations if isinstance(d, FlowDecl)]
    assert len(pages) == 1 and pages[0].name == "home"
    assert len(flows) == 1 and flows[0].name == "chat"
    step = flows[0].steps[0]
    assert step.kind == "ai"
    assert step.target == "support_bot"


def test_comments_do_not_break_indentation():
    code = dedent(
        '''
        page is "home" at "/":
          # comment
          section is "hero":
            text is "Hi"  # inline

        # between decls
        flow is "chat":
          step is "answer":
            kind is "ai"
            target is "support_bot"
        '''
    )
    module = parser.parse_source(code)
    pages = [d for d in module.declarations if isinstance(d, PageDecl)]
    flows = [d for d in module.declarations if isinstance(d, FlowDecl)]
    assert pages and flows
    # section should be parsed despite surrounding comments
    section_nodes = [el for el in pages[0].layout if hasattr(el, "name")]
    assert section_nodes and section_nodes[0].name == "hero"
    assert flows[0].steps[0].kind == "ai"
