"""
Namel3ss V3 core package.
"""

from .version import __version__  # noqa: F401

__all__ = [
    "lexer",
    "parser",
    "ast_nodes",
    "ir",
    "errors",
    "typesys",
    "__version__",
]
