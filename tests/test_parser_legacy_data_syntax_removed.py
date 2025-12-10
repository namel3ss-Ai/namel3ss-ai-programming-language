import pytest

from namel3ss.errors import ParseError
from namel3ss.parser import parse_source


def _assert_legacy_rejected(source: str):
    with pytest.raises(ParseError) as excinfo:
        parse_source(source)
    msg = str(excinfo.value)
    assert "pipeline" in msg or "keep rows where" in msg
    return msg


def test_reject_all_from_where():
    src = (
        'flow is "f":\n'
        '  step is "s":\n'
        '    let filtered be all row from sales_data where row.country is "BE"\n'
    )
    msg = _assert_legacy_rejected(src)
    assert "all" in msg


def test_reject_all_without_let():
    src = (
        'flow is "f":\n'
        '  step is "s":\n'
        '    all item from [1, 2, 3] where item > 0\n'
    )
    msg = _assert_legacy_rejected(src)
    assert "all" in msg


def test_reject_all_field_projection():
    src = (
        'flow is "f":\n'
        '  step is "s":\n'
        "    let emails be all user.email from users\n"
    )
    msg = _assert_legacy_rejected(src)
    assert "all" in msg


def test_reject_map_function_call():
    src = (
        'flow is "f":\n'
        '  step is "s":\n'
        "    let doubled be map(xs, to: item * 2)\n"
    )
    msg = _assert_legacy_rejected(src)
    assert "map" in msg


def test_reject_sum_of_all():
    src = (
        'flow is "f":\n'
        '  step is "s":\n'
        "    let total be sum of all row.amount from sales_data\n"
    )
    msg = _assert_legacy_rejected(src)
    assert "sum" in msg or "all" in msg
