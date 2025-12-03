"""
Simple deprecation helpers for RC hardening.
"""

from __future__ import annotations

import functools
import warnings
from dataclasses import dataclass
from typing import Callable, TypeVar

F = TypeVar("F", bound=Callable[..., object])


@dataclass
class DeprecatedRoute:
    name: str
    reason: str


def deprecated(reason: str) -> Callable[[F], F]:
    """
    Decorator to mark functions or routes as deprecated.
    Emits a DeprecationWarning and annotates the function for inspection.
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):  # type: ignore[override]
            warnings.warn(f"{func.__name__} is deprecated: {reason}", DeprecationWarning, stacklevel=2)
            return func(*args, **kwargs)

        setattr(wrapper, "__deprecated__", True)
        setattr(wrapper, "__deprecation_reason__", reason)
        return wrapper  # type: ignore[return-value]

    return decorator
