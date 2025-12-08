import pytest

from namel3ss import parser, ir, errors


def test_navigate_missing_target_errors():
    with pytest.raises(errors.ParseError) as exc:
        parser.parse_source(
            '''
page "home" at "/":
  section "main":
    button "Go":
      on click:
        navigate to
'''
        )
    assert "N3L-950" in str(exc.value)


def test_navigate_unknown_page_errors_in_ir():
    mod = parser.parse_source(
        '''
page "home" at "/":
  section "main":
    button "Go":
      on click:
        navigate to page "chat"
'''
    )
    with pytest.raises(ir.IRError) as exc:
        ir.ast_to_ir(mod)
    assert "N3L-1301" in str(exc.value)


def test_navigate_and_flow_not_allowed_together():
    with pytest.raises(errors.ParseError) as exc:
        parser.parse_source(
            '''
page "home" at "/":
  section "main":
    button "Go":
      on click:
        do flow "start_chat"
        navigate to page "chat"
'''
        )
    assert "N3L-1300" in str(exc.value)
