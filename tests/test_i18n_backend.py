from namel3ss.i18n import translate


def test_translate_returns_language_value():
    assert translate("error.memory.forbidden", "fr").startswith("Vous")
    assert translate("error.memory.forbidden", "en").startswith("You")


def test_translate_fallback_to_key_when_missing():
    assert translate("missing.key", "fr") == "missing.key"
