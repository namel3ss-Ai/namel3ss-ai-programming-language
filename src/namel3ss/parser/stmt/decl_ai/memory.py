"""Memory block parsing helpers extracted from the legacy parser."""

from __future__ import annotations

from .... import ast_nodes
from ....lexer import Token
from ....parser.tokens import SUPPORTED_MEMORY_KINDS

__all__ = ["_parse_memory_block", "_suggest_memory_kind"]

def _parse_memory_block(self, owner_label: str, field_token: Token) -> ast_nodes.AiMemoryConfig:
    start_span = self._span(field_token)
    self.consume("COLON")
    self.consume("NEWLINE")
    self.consume("INDENT")
    mem_kind: str | None = None
    mem_window: int | None = None
    mem_store: str | None = None
    short_term_cfg: ast_nodes.AiShortTermMemoryConfig | None = None
    long_term_cfg: ast_nodes.AiLongTermMemoryConfig | None = None
    episodic_cfg: ast_nodes.AiEpisodicMemoryConfig | None = None
    semantic_cfg: ast_nodes.AiSemanticMemoryConfig | None = None
    profile_cfg: ast_nodes.AiProfileMemoryConfig | None = None
    recall_rules: list[ast_nodes.AiRecallRule] = []
    while not self.check("DEDENT"):
        if self.match("NEWLINE"):
            continue
        mem_field = self.consume_any({"KEYWORD", "IDENT"})
        field_name = mem_field.value or ""
        if field_name == "kind":
            self.consume("KEYWORD", "is")
            kind_tok = self.consume("STRING")
            mem_kind = kind_tok.value or ""
        elif field_name == "window":
            self.consume("KEYWORD", "is")
            num_tok = self.consume("NUMBER")
            mem_window = self._consume_positive_int(
                num_tok, "N3L-1202: memory window must be a positive integer."
            )
        elif field_name == "store":
            self.consume("KEYWORD", "is")
            store_tok = self.consume("STRING")
            mem_store = store_tok.value or ""
            if not mem_store:
                raise self.error("N3L-1203: memory store must be a non-empty string.", store_tok)
        elif field_name == "kinds":
            (
                short_term_cfg,
                long_term_cfg,
                episodic_cfg,
                semantic_cfg,
                profile_cfg,
            ) = self._parse_memory_kinds_block(owner_label)
            continue
        elif field_name == "recall":
            recall_rules = self._parse_memory_recall_block()
            continue
        else:
            raise self.error(f"Unexpected field '{field_name}' in memory block", mem_field)
        self.optional_newline()
    self.consume("DEDENT")
    self.optional_newline()
    return ast_nodes.AiMemoryConfig(
        kind=mem_kind,
        window=mem_window,
        store=mem_store,
        short_term=short_term_cfg,
        long_term=long_term_cfg,
        episodic=episodic_cfg,
        semantic=semantic_cfg,
        profile=profile_cfg,
        recall=recall_rules,
        span=start_span,
    )

def _suggest_memory_kind(self, name: str) -> str | None:
    matches = get_close_matches(name, SUPPORTED_MEMORY_KINDS, n=1, cutoff=0.6)
    return matches[0] if matches else None

