from namel3ss import parser, ast_nodes


def _first_page(mod):
    return next(decl for decl in mod.declarations if isinstance(decl, ast_nodes.PageDecl))


def test_navigate_path_parses():
    mod = parser.parse_source(
        '''
page "home" at "/":
  section "main":
    button "Go":
      on click:
        navigate to "/chat"
'''
    )
    page = _first_page(mod)
    btn = page.layout[0].components[0]
    action = btn.handler.actions[0]
    assert isinstance(action, ast_nodes.NavigateAction)
    assert action.target_path == "/chat"
    assert action.target_page_name is None


def test_navigate_path_is_parses():
    mod = parser.parse_source(
        '''
page is "home" at "/":
  section is "main":
    button is "Go":
      on click:
        navigate "/chat"
'''
    )
    btn = _first_page(mod).layout[0].components[0]
    action = btn.handler.actions[0]
    assert action.target_path == "/chat"
    assert action.target_page_name is None


def test_navigate_page_parses():
    mod = parser.parse_source(
        '''
page "home" at "/":
  section "main":
    button "Go":
      on click:
        navigate to page "chat"
'''
    )
    btn = _first_page(mod).layout[0].components[0]
    action = btn.handler.actions[0]
    assert action.target_page_name == "chat"
    assert action.target_path is None


def test_navigate_page_is_parses():
    mod = parser.parse_source(
        '''
page is "home" at "/":
  section is "main":
    button is "Go":
      on click:
        navigate to page is "chat"
'''
    )
    btn = _first_page(mod).layout[0].components[0]
    action = btn.handler.actions[0]
    assert action.target_page_name == "chat"
    assert action.target_path is None

