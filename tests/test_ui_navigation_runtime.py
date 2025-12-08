from namel3ss import parser, ir
from namel3ss.ui.runtime import UIPresenter, Router, handle_ui_action


SOURCE_PATH = """
page is "home" at "/":
  section is "main":
    button is "Go to Chat":
      on click:
        navigate to "/chat"

page is "chat" at "/chat":
  section is "main":
    button is "Back":
      on click:
        navigate to "/"
"""


SOURCE_PAGE = """
page is "home" at "/":
  section is "main":
    button is "Go to Chat":
      on click:
        navigate to page is "chat"

page is "chat" at "/chat":
  section is "main":
    button is "Back":
      on click:
        navigate to page is "home"
"""


def _prepare(source: str):
    module = parser.parse_source(source)
    program = ir.ast_to_ir(module)
    router = Router(program, initial_path="/")
    current_page = router.get_current_page()
    presenter = UIPresenter(current_page)
    return router, presenter


def test_navigation_by_path_updates_router():
    router, presenter = _prepare(SOURCE_PATH)
    presenter.click("Go to Chat", dispatcher=lambda act, _: handle_ui_action(act, router))
    assert router.state.current_path == "/chat"
    page = router.get_current_page()
    assert page is not None
    assert page.name == "chat"


def test_navigation_by_page_name_updates_router():
    router, presenter = _prepare(SOURCE_PAGE)
    presenter.click("Go to Chat", dispatcher=lambda act, _: handle_ui_action(act, router))
    assert router.state.current_path == "/chat"
    page = router.get_current_page()
    assert page is not None
    assert page.name == "chat"
