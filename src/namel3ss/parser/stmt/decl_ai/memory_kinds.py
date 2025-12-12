"""Memory kinds parsing helpers extracted from the legacy parser."""

from __future__ import annotations

from .... import ast_nodes
from ....lexer import Token
from ....parser.tokens import SUPPORTED_MEMORY_KINDS

__all__ = [
"_parse_memory_kinds_block",
"_parse_short_term_kind",
"_parse_long_term_kind",
"_parse_profile_kind",
"_parse_episodic_kind",
"_parse_semantic_kind",
"_parse_time_decay_block",
]

def _parse_memory_kinds_block(
    self,
    owner_label: str,
) -> tuple[
    ast_nodes.AiShortTermMemoryConfig | None,
    ast_nodes.AiLongTermMemoryConfig | None,
    ast_nodes.AiEpisodicMemoryConfig | None,
    ast_nodes.AiSemanticMemoryConfig | None,
    ast_nodes.AiProfileMemoryConfig | None,
]:
    self.consume("COLON")
    self.consume("NEWLINE")
    self.consume("INDENT")
    short_term_cfg: ast_nodes.AiShortTermMemoryConfig | None = None
    long_term_cfg: ast_nodes.AiLongTermMemoryConfig | None = None
    episodic_cfg: ast_nodes.AiEpisodicMemoryConfig | None = None
    semantic_cfg: ast_nodes.AiSemanticMemoryConfig | None = None
    profile_cfg: ast_nodes.AiProfileMemoryConfig | None = None
    defined_kinds: set[str] = set()
    while not self.check("DEDENT"):
        if self.match("NEWLINE"):
            continue
        kind_tok = self.consume_any({"KEYWORD", "IDENT"})
        kind_name_raw = kind_tok.value or ""
        kind_name = (kind_name_raw or "").strip()
        bare_entry = False
        if not kind_name:
            raise self.error("Memory kind name cannot be empty.", kind_tok)
        if kind_name not in SUPPORTED_MEMORY_KINDS:
            suggestion = self._suggest_memory_kind(kind_name)
            hint = f" Did you mean '{suggestion}'?" if suggestion else ""
            raise self.error(
                f"Memory kind '{kind_name}' is not supported.{hint} Supported kinds are: {', '.join(SUPPORTED_MEMORY_KINDS)}.",
                kind_tok,
            )
        if kind_name in defined_kinds:
            raise self.error(
                f"Memory kind '{kind_name}' is declared more than once for {owner_label}. Combine your settings into a single entry.",
                kind_tok,
            )
        bare_entry = False
        if self.match("COLON"):
            self.consume("NEWLINE")
            if self.check("INDENT"):
                self.consume("INDENT")
                if self.check("DEDENT"):
                    self.consume("DEDENT")
                    bare_entry = True
                else:
                    if kind_name == "short_term":
                        if short_term_cfg is not None:
                            raise self.error("short_term memory kind may only be defined once.", kind_tok)
                        short_term_cfg = self._parse_short_term_kind(owner_label)
                    elif kind_name == "long_term":
                        if long_term_cfg is not None:
                            raise self.error("long_term memory kind may only be defined once.", kind_tok)
                        long_term_cfg = self._parse_long_term_kind(owner_label)
                    elif kind_name == "episodic":
                        if episodic_cfg is not None:
                            raise self.error("episodic memory kind may only be defined once.", kind_tok)
                        episodic_cfg = self._parse_episodic_kind(owner_label)
                    elif kind_name == "semantic":
                        if semantic_cfg is not None:
                            raise self.error("semantic memory kind may only be defined once.", kind_tok)
                        semantic_cfg = self._parse_semantic_kind(owner_label)
                    elif kind_name == "profile":
                        if profile_cfg is not None:
                            raise self.error("profile memory kind may only be defined once.", kind_tok)
                        profile_cfg = self._parse_profile_kind(owner_label)
                    self.consume("DEDENT")
            else:
                bare_entry = True
        else:
            bare_entry = True

        if bare_entry:
            if kind_name == "short_term":
                if short_term_cfg is not None:
                    raise self.error("short_term memory kind may only be defined once.", kind_tok)
                short_term_cfg = ast_nodes.AiShortTermMemoryConfig(span=self._span(kind_tok))
            elif kind_name == "long_term":
                if long_term_cfg is not None:
                    raise self.error("long_term memory kind may only be defined once.", kind_tok)
                long_term_cfg = ast_nodes.AiLongTermMemoryConfig(span=self._span(kind_tok))
            elif kind_name == "episodic":
                if episodic_cfg is not None:
                    raise self.error("episodic memory kind may only be defined once.", kind_tok)
                episodic_cfg = ast_nodes.AiEpisodicMemoryConfig(span=self._span(kind_tok))
            elif kind_name == "semantic":
                if semantic_cfg is not None:
                    raise self.error("semantic memory kind may only be defined once.", kind_tok)
                semantic_cfg = ast_nodes.AiSemanticMemoryConfig(span=self._span(kind_tok))
            elif kind_name == "profile":
                if profile_cfg is not None:
                    raise self.error("profile memory kind may only be defined once.", kind_tok)
                profile_cfg = ast_nodes.AiProfileMemoryConfig(span=self._span(kind_tok))
        defined_kinds.add(kind_name)
        self.optional_newline()
    self.consume("DEDENT")
    self.optional_newline()
    return short_term_cfg, long_term_cfg, episodic_cfg, semantic_cfg, profile_cfg

def _parse_short_term_kind(self, owner_label: str) -> ast_nodes.AiShortTermMemoryConfig:
    window: int | None = None
    store: str | None = None
    retention_days: int | None = None
    pii_policy: str | None = None
    scope: str | None = None
    pipeline: list[ast_nodes.AiMemoryPipelineStep] | None = None
    while not self.check("DEDENT"):
        if self.match("NEWLINE"):
            continue
        field_tok = self.consume_any({"KEYWORD", "IDENT"})
        field_name = field_tok.value or ""
        if field_name == "window":
            self.consume("KEYWORD", "is")
            num_tok = self.consume("NUMBER")
            window = self._consume_positive_int(
                num_tok, "N3L-1202: memory window must be a positive integer."
            )
        elif field_name == "store":
            self.consume("KEYWORD", "is")
            store_tok = self.consume("STRING")
            store = store_tok.value or ""
            if not store:
                raise self.error("N3L-1203: memory store must be a non-empty string.", store_tok)
        elif field_name == "retention_days":
            self.consume("KEYWORD", "is")
            num_tok = self.consume("NUMBER")
            retention_days = self._consume_positive_int(
                num_tok, "N3L-1202: retention_days must be a positive integer."
            )
        elif field_name == "pii_policy":
            self.consume("KEYWORD", "is")
            policy_tok = self.consume("STRING")
            pii_policy = (policy_tok.value or "").strip()
        elif field_name == "scope":
            self.consume("KEYWORD", "is")
            scope_tok = self.consume("STRING")
            scope = (scope_tok.value or "").strip()
        elif field_name == "pipeline":
            pipeline = self._parse_memory_pipeline_block()
        else:
            raise self.error(f"Unexpected field '{field_name}' in short_term memory kind.", field_tok)
        self.optional_newline()
    return ast_nodes.AiShortTermMemoryConfig(
        window=window,
        store=store,
        retention_days=retention_days,
        pii_policy=pii_policy,
        scope=scope,
        pipeline=pipeline,
    )

def _parse_long_term_kind(self, owner_label: str) -> ast_nodes.AiLongTermMemoryConfig:
    store: str | None = None
    pipeline: list[ast_nodes.AiMemoryPipelineStep] | None = None
    retention_days: int | None = None
    pii_policy: str | None = None
    scope: str | None = None
    time_decay: ast_nodes.AiTimeDecayConfig | None = None
    while not self.check("DEDENT"):
        if self.match("NEWLINE"):
            continue
        field_tok = self.consume_any({"KEYWORD", "IDENT"})
        field_name = field_tok.value or ""
        if field_name == "store":
            self.consume("KEYWORD", "is")
            store_tok = self.consume("STRING")
            store = store_tok.value or ""
            if not store:
                raise self.error("N3L-1203: memory store must be a non-empty string.", store_tok)
        elif field_name == "pipeline":
            pipeline = self._parse_memory_pipeline_block()
        elif field_name == "retention_days":
            self.consume("KEYWORD", "is")
            num_tok = self.consume("NUMBER")
            retention_days = self._consume_positive_int(
                num_tok, "N3L-1202: retention_days must be a positive integer."
            )
        elif field_name == "pii_policy":
            self.consume("KEYWORD", "is")
            policy_tok = self.consume("STRING")
            pii_policy = (policy_tok.value or "").strip()
        elif field_name == "scope":
            self.consume("KEYWORD", "is")
            scope_tok = self.consume("STRING")
            scope = (scope_tok.value or "").strip()
        elif field_name == "time_decay":
            if time_decay is not None:
                raise self.error("time_decay may only be defined once in a long_term block.", field_tok)
            time_decay = self._parse_time_decay_block("long_term", field_tok)
        else:
            raise self.error(f"Unexpected field '{field_name}' in long_term memory kind.", field_tok)
        self.optional_newline()
    if not store:
        raise self.error(
            f"long_term memory kind on {owner_label} requires a 'store is \"...\"' entry.",
            self.peek(),
        )
    return ast_nodes.AiLongTermMemoryConfig(
        store=store,
        pipeline=pipeline,
        retention_days=retention_days,
        pii_policy=pii_policy,
        scope=scope,
        time_decay=time_decay,
    )

def _parse_profile_kind(self, owner_label: str) -> ast_nodes.AiProfileMemoryConfig:
    store: str | None = None
    extract_facts: bool | None = None
    pipeline: list[ast_nodes.AiMemoryPipelineStep] | None = None
    retention_days: int | None = None
    pii_policy: str | None = None
    scope: str | None = None
    while not self.check("DEDENT"):
        if self.match("NEWLINE"):
            continue
        field_tok = self.consume_any({"KEYWORD", "IDENT"})
        field_name = field_tok.value or ""
        if field_name == "store":
            self.consume("KEYWORD", "is")
            store_tok = self.consume("STRING")
            store = store_tok.value or ""
            if not store:
                raise self.error("N3L-1203: memory store must be a non-empty string.", store_tok)
        elif field_name == "extract_facts":
            self.consume("KEYWORD", "is")
            bool_tok = self.consume_any({"KEYWORD", "IDENT"})
            extract_facts = self._consume_bool_literal(
                bool_tok, "extract_facts must be true or false."
            )
        elif field_name == "pipeline":
            pipeline = self._parse_memory_pipeline_block()
        elif field_name == "retention_days":
            self.consume("KEYWORD", "is")
            num_tok = self.consume("NUMBER")
            retention_days = self._consume_positive_int(
                num_tok, "N3L-1202: retention_days must be a positive integer."
            )
        elif field_name == "pii_policy":
            self.consume("KEYWORD", "is")
            policy_tok = self.consume("STRING")
            pii_policy = (policy_tok.value or "").strip()
        elif field_name == "scope":
            self.consume("KEYWORD", "is")
            scope_tok = self.consume("STRING")
            scope = (scope_tok.value or "").strip()
        else:
            raise self.error(f"Unexpected field '{field_name}' in profile memory kind.", field_tok)
        self.optional_newline()
    if not store:
        raise self.error(
            f"profile memory kind on {owner_label} requires a 'store is \"...\"' entry.",
            self.peek(),
        )
    return ast_nodes.AiProfileMemoryConfig(
        store=store,
        extract_facts=extract_facts,
        pipeline=pipeline,
        retention_days=retention_days,
        pii_policy=pii_policy,
        scope=scope,
    )

def _parse_episodic_kind(self, owner_label: str) -> ast_nodes.AiEpisodicMemoryConfig:
    store: str | None = None
    retention_days: int | None = None
    pii_policy: str | None = None
    scope: str | None = None
    pipeline: list[ast_nodes.AiMemoryPipelineStep] | None = None
    time_decay: ast_nodes.AiTimeDecayConfig | None = None
    while not self.check("DEDENT"):
        if self.match("NEWLINE"):
            continue
        field_tok = self.consume_any({"KEYWORD", "IDENT"})
        field_name = field_tok.value or ""
        if field_name == "store":
            self.consume("KEYWORD", "is")
            store_tok = self.consume("STRING")
            store = store_tok.value or ""
            if not store:
                raise self.error("N3L-1203: memory store must be a non-empty string.", store_tok)
        elif field_name == "retention_days":
            self.consume("KEYWORD", "is")
            num_tok = self.consume("NUMBER")
            retention_days = self._consume_positive_int(
                num_tok, "N3L-1202: retention_days must be a positive integer."
            )
        elif field_name == "pii_policy":
            self.consume("KEYWORD", "is")
            policy_tok = self.consume("STRING")
            pii_policy = (policy_tok.value or "").strip()
        elif field_name == "scope":
            self.consume("KEYWORD", "is")
            scope_tok = self.consume("STRING")
            scope = (scope_tok.value or "").strip()
        elif field_name == "pipeline":
            pipeline = self._parse_memory_pipeline_block()
        elif field_name == "time_decay":
            if time_decay is not None:
                raise self.error("time_decay may only be defined once in an episodic block.", field_tok)
            time_decay = self._parse_time_decay_block("episodic", field_tok)
        else:
            raise self.error(f"Unexpected field '{field_name}' in episodic memory kind.", field_tok)
        self.optional_newline()
    return ast_nodes.AiEpisodicMemoryConfig(
        store=store,
        retention_days=retention_days,
        pii_policy=pii_policy,
        scope=scope,
        pipeline=pipeline,
        time_decay=time_decay,
    )

def _parse_semantic_kind(self, owner_label: str) -> ast_nodes.AiSemanticMemoryConfig:
    store: str | None = None
    retention_days: int | None = None
    pii_policy: str | None = None
    scope: str | None = None
    pipeline: list[ast_nodes.AiMemoryPipelineStep] | None = None
    time_decay: ast_nodes.AiTimeDecayConfig | None = None
    while not self.check("DEDENT"):
        if self.match("NEWLINE"):
            continue
        field_tok = self.consume_any({"KEYWORD", "IDENT"})
        field_name = field_tok.value or ""
        if field_name == "store":
            self.consume("KEYWORD", "is")
            store_tok = self.consume("STRING")
            store = store_tok.value or ""
            if not store:
                raise self.error("N3L-1203: memory store must be a non-empty string.", store_tok)
        elif field_name == "retention_days":
            self.consume("KEYWORD", "is")
            num_tok = self.consume("NUMBER")
            retention_days = self._consume_positive_int(
                num_tok, "N3L-1202: retention_days must be a positive integer."
            )
        elif field_name == "pii_policy":
            self.consume("KEYWORD", "is")
            policy_tok = self.consume("STRING")
            pii_policy = (policy_tok.value or "").strip()
        elif field_name == "scope":
            self.consume("KEYWORD", "is")
            scope_tok = self.consume("STRING")
            scope = (scope_tok.value or "").strip()
        elif field_name == "pipeline":
            pipeline = self._parse_memory_pipeline_block()
        elif field_name == "time_decay":
            if time_decay is not None:
                raise self.error("time_decay may only be defined once in a semantic block.", field_tok)
            time_decay = self._parse_time_decay_block("semantic", field_tok)
        else:
            raise self.error(f"Unexpected field '{field_name}' in semantic memory kind.", field_tok)
        self.optional_newline()
    return ast_nodes.AiSemanticMemoryConfig(
        store=store,
        retention_days=retention_days,
        pii_policy=pii_policy,
        scope=scope,
        pipeline=pipeline,
        time_decay=time_decay,
    )

def _parse_time_decay_block(self, kind_name: str, field_token: Token) -> ast_nodes.AiTimeDecayConfig:
    if self.match_value("KEYWORD", "is"):
        raise self.error(
            f"time_decay on {kind_name} memory uses block syntax. Try:\n  time_decay:\n    half_life_days is 30",
            field_token,
        )
    self.consume("COLON")
    self.consume("NEWLINE")
    self.consume("INDENT")
    half_life_days: int | None = None
    while not self.check("DEDENT"):
        if self.match("NEWLINE"):
            continue
        inner_tok = self.consume_any({"KEYWORD", "IDENT"})
        inner_name = inner_tok.value or ""
        if inner_name == "half_life_days":
            self.consume("KEYWORD", "is")
            num_tok = self.consume("NUMBER")
            half_life_days = self._consume_positive_int(
                num_tok, "time_decay half_life_days must be a positive integer."
            )
        else:
            raise self.error(
                f"Unknown field '{inner_name}' inside time_decay for {kind_name} memory. Supported: half_life_days.",
                inner_tok,
            )
        self.optional_newline()
    self.consume("DEDENT")
    if half_life_days is None:
        raise self.error(
            f"time_decay on {kind_name} memory requires 'half_life_days is <number>'.",
            field_token,
        )
    return ast_nodes.AiTimeDecayConfig(half_life_days=half_life_days, span=self._span(field_token))

