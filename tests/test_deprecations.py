import warnings

from namel3ss.deprecations import DeprecatedRoute, deprecated


def test_deprecated_decorator_emits_warning_and_marks_function():
    calls = []

    @deprecated("use new_func")
    def old():
        calls.append(True)
        return "ok"

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = old()
    assert result == "ok"
    assert calls
    assert getattr(old, "__deprecated__", False) is True
    assert getattr(old, "__deprecation_reason__", "") == "use new_func"
    assert any(item.category is DeprecationWarning for item in w)


def test_deprecated_route_dataclass():
    route = DeprecatedRoute(name="/api/old", reason="superseded")
    assert route.name == "/api/old"
    assert "superseded" in route.reason
