"""
Line-oriented lexer for the Namel3ss V3 language.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .errors import LexError

KEYWORDS = {
    "use",
    "app",
    "page",
    "flow",
    "step",
    "kind",
    "target",
    "plugin",
    "model",
    "ai",
    "ai_call",
    "agent",
    "memory",
    "section",
    "component",
    "value",
    "variant",
    "items",
    "body",
    "description",
    "entry_page",
    "title",
    "route",
    "provider",
    "input",
    "from",
    "goal",
    "personality",
    "type",
    # English-style surface syntax
    "remember",
    "conversation",
    "as",
    "provided",
    "by",
    "when",
    "called",
    "comes",
    "describe",
    "task",
    "the",
    "is",
    "this",
    "will",
    "first",
    "then",
    "finally",
    "starts",
    "at",
    "found",
    "titled",
    "show",
    "text",
    "form",
    "asking",
    "do",
    "with",
    "message",
}


@dataclass
class Token:
    type: str
    value: Optional[str]
    line: int
    column: int

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"Token({self.type}, {self.value}, {self.line}:{self.column})"


class Lexer:
    """
    Very small lexer that emits indentation-sensitive tokens.
    """

    def __init__(self, source: str, filename: str = "<string>") -> None:
        self.source = source
        self.filename = filename

    def tokenize(self) -> List[Token]:
        tokens: List[Token] = []
        indent_stack = [0]
        lines = self.source.splitlines()
        for line_no, raw_line in enumerate(lines, start=1):
            if not raw_line.strip():
                continue

            indent = self._count_indent(raw_line, line_no)
            current_indent = indent_stack[-1]
            if indent > current_indent:
                indent_stack.append(indent)
                tokens.append(Token("INDENT", None, line_no, 1))
            else:
                while indent < current_indent:
                    indent_stack.pop()
                    tokens.append(Token("DEDENT", None, line_no, 1))
                    current_indent = indent_stack[-1]
                if indent != current_indent:
                    raise LexError(
                        f"Inconsistent indentation: expected {current_indent}, found {indent}",
                        line_no,
                        1,
                    )

            line_tokens = self._tokenize_line(raw_line[indent:], line_no, indent + 1)
            tokens.extend(line_tokens)

        while len(indent_stack) > 1:
            indent_stack.pop()
            tokens.append(Token("DEDENT", None, len(lines) + 1, 1))
        tokens.append(Token("EOF", None, len(lines) + 1, 1))
        return tokens

    def _count_indent(self, line: str, line_no: int) -> int:
        indent = 0
        for char in line:
            if char == " ":
                indent += 1
            elif char == "\t":
                raise LexError("Tabs are not allowed for indentation", line_no, 1)
            else:
                break
        return indent

    def _tokenize_line(self, line: str, line_no: int, column_offset: int) -> List[Token]:
        tokens: List[Token] = []
        i = 0
        column = column_offset

        while i < len(line):
            char = line[i]
            if char == " ":
                i += 1
                column += 1
                continue
            if char == '"':
                start_col = column
                i += 1
                column += 1
                value_chars = []
                while i < len(line) and line[i] != '"':
                    value_chars.append(line[i])
                    i += 1
                    column += 1
                if i >= len(line):
                    raise LexError("Unterminated string literal", line_no, start_col)
                i += 1
                column += 1
                tokens.append(
                    Token("STRING", "".join(value_chars), line_no, start_col)
                )
                continue
            if char.isalpha() or char == "_":
                start_col = column
                ident_chars = [char]
                i += 1
                column += 1
                while i < len(line) and (line[i].isalnum() or line[i] == "_"):
                    ident_chars.append(line[i])
                    i += 1
                    column += 1
                ident = "".join(ident_chars)
                token_type = "KEYWORD" if ident in KEYWORDS else "IDENT"
                tokens.append(Token(token_type, ident, line_no, start_col))
                continue
            if char == ":":
                tokens.append(Token("COLON", ":", line_no, column))
                i += 1
                column += 1
                continue
            raise LexError(f"Unexpected character '{char}'", line_no, column)

        tokens.append(Token("NEWLINE", None, line_no, column))
        return tokens
