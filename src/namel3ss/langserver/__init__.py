"""
Lightweight Language Server Protocol implementation for Namel3ss.

This module exposes a minimal server that speaks LSP over stdio and reuses
the existing parser, diagnostics runner, and formatter.
"""

from .server import LanguageServer

__all__ = ["LanguageServer"]
