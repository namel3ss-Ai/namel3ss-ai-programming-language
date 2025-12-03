from namel3ss.plugins.versioning import is_compatible, parse_version


def test_parse_version_valid():
    assert parse_version("1.2.3") == (1, 2, 3)


def test_is_compatible_exact_and_range():
    assert is_compatible("3.0.0", "3.0.0")
    assert is_compatible("3.2.0", ">=3.0.0,<4.0.0")
    assert not is_compatible("2.9.0", ">=3.0.0,<4.0.0")
    assert not is_compatible("4.0.0", ">=3.0.0,<4.0.0")
