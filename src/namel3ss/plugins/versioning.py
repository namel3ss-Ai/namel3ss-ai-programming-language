"""
Semantic version parsing and compatibility helpers.
"""

from __future__ import annotations

import re
from typing import Tuple

from ..version import __version__

CORE_VERSION = __version__


def parse_version(version: str) -> Tuple[int, int, int]:
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)", version)
    if not match:
        raise ValueError(f"Invalid version string '{version}'")
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch)


def _compare(v1: Tuple[int, int, int], v2: Tuple[int, int, int]) -> int:
    if v1 == v2:
        return 0
    if v1 > v2:
        return 1
    return -1


def is_compatible(core_version: str, requirement: str) -> bool:
    """
    Check if core_version satisfies a semver range expressed as a comma-separated list of comparators.
    Supported comparators: >=, >, <=, <, ==.
    """

    core = parse_version(core_version)
    parts = [p.strip() for p in requirement.split(",") if p.strip()]
    if not parts:
        return True
    for part in parts:
        if part.startswith(">="):
            if _compare(core, parse_version(part[2:])) < 0:
                return False
        elif part.startswith("<="):
            if _compare(core, parse_version(part[2:])) > 0:
                return False
        elif part.startswith(">"):
            if _compare(core, parse_version(part[1:])) <= 0:
                return False
        elif part.startswith("<"):
            if _compare(core, parse_version(part[1:])) >= 0:
                return False
        elif part.startswith("=="):
            if _compare(core, parse_version(part[2:])) != 0:
                return False
        else:
            # exact match fallback
            if _compare(core, parse_version(part)) != 0:
                return False
    return True
