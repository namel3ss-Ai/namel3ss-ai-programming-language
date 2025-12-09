from __future__ import annotations

import logging
import os
import warnings
import contextlib

log = logging.getLogger(__name__)


class DeprecationStrictError(RuntimeError):
    """Raised when a deprecated feature is used and strict mode is enabled."""


def warn_deprecated(feature: str, *, remove_in: str, code: str, details: str | None = None) -> None:
    """
    Emit a structured deprecation warning.

    If N3_DEPRECATION_STRICT=true, raise DeprecationStrictError instead of warning.
    """

    message = f"{feature} is deprecated and will be removed in {remove_in} (code={code})."
    if details:
        message = f"{message} {details}"
    strict = str(os.getenv("N3_DEPRECATION_STRICT", "")).strip().lower() in {"1", "true", "yes", "on"}
    if strict:
        raise DeprecationStrictError(message)
    warnings.warn(message, DeprecationWarning, stacklevel=2)
    with contextlib.suppress(Exception):  # pragma: no cover - logging fallback
        log.warning("DEPRECATION: %s", message)
