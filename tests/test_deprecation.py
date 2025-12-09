import os
import warnings

import pytest

from namel3ss.runtime.deprecation import DeprecationStrictError, warn_deprecated


def test_warn_deprecated_emits_warning(monkeypatch):
    monkeypatch.delenv("N3_DEPRECATION_STRICT", raising=False)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        warn_deprecated("legacy-field", remove_in="1.0.0", code="N3-DEPR-TEST")
    assert any(isinstance(w.message, DeprecationWarning) for w in caught)


def test_warn_deprecated_strict_raises(monkeypatch):
    monkeypatch.setenv("N3_DEPRECATION_STRICT", "true")
    with pytest.raises(DeprecationStrictError):
        warn_deprecated("legacy-field", remove_in="1.0.0", code="N3-DEPR-TEST")
