"""Memory recall and pipeline helpers extracted from the legacy parser."""

from __future__ import annotations

from .... import ast_nodes
from ....lexer import Token
from ....parser.tokens import SUPPORTED_MEMORY_KINDS

__all__ = [
"_parse_memory_recall_block",
"_parse_memory_pipeline_block",
"_parse_block_pipeline_step",
"_parse_legacy_pipeline_step",
"_assign_pipeline_step_field",
"_finalize_pipeline_step",
"_consume_positive_int",
"_consume_bool_literal",
]

def _parse_memory_recall_block(self) -> list[ast_nodes.AiRecallRule]:
    self.consume("COLON")
    self.consume("NEWLINE")
    self.consume("INDENT")
    rules: list[ast_nodes.AiRecallRule] = []
    while not self.check("DEDENT"):
        if self.match("NEWLINE"):
            continue
        self.consume("DASH")
        rule = ast_nodes.AiRecallRule()
        start_tok = self.peek()
        nested_indent = 0
        while True:
            if nested_indent == 0 and (self.check("DEDENT") or self.check("DASH")):
                break
            if self.match("NEWLINE"):
                continue
            if self.match("INDENT"):
                nested_indent += 1
                continue
            if nested_indent > 0 and self.match("DEDENT"):
                nested_indent -= 1
                continue
            field_tok = self.consume_any({"KEYWORD", "IDENT"})
            field_name = field_tok.value or ""
            if field_name == "source":
                self.consume("KEYWORD", "is")
                source_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                rule.source = ((source_tok.value or "").strip()).lower()
                if rule.source not in SUPPORTED_MEMORY_KINDS:
                    suggestion = self._suggest_memory_kind(rule.source)
                    hint = f" Did you mean '{suggestion}'?" if suggestion else ""
                    raise self.error(
                        f"N3L-1202: Memory recall source '{rule.source}' is not a supported memory kind.{hint} Supported kinds are: {', '.join(SUPPORTED_MEMORY_KINDS)}.",
                        source_tok,
                    )
            elif field_name == "count":
                self.consume("KEYWORD", "is")
                num_tok = self.consume("NUMBER")
                rule.count = self._consume_positive_int(
                    num_tok, "N3L-1202: memory count must be a positive integer."
                )
            elif field_name == "top_k":
                self.consume("KEYWORD", "is")
                num_tok = self.consume("NUMBER")
                rule.top_k = self._consume_positive_int(
                    num_tok, "N3L-1202: memory top_k must be a positive integer."
                )
            elif field_name == "include":
                self.consume("KEYWORD", "is")
                bool_tok = self.consume_any({"KEYWORD", "IDENT"})
                rule.include = self._consume_bool_literal(
                    bool_tok, "include must be true or false."
                )
            else:
                raise self.error(f"Unexpected field '{field_name}' in recall rule.", field_tok)
            self.optional_newline()
        if not rule.source:
            raise self.error("Recall rule must specify a source.", start_tok)
        if nested_indent != 0:
            raise self.error("Incomplete recall rule indentation.", self.peek())
        rules.append(rule)
    self.consume("DEDENT")
    self.optional_newline()
    return rules

def _parse_memory_pipeline_block(self) -> list[ast_nodes.AiMemoryPipelineStep]:
    self.consume("COLON")
    self.consume("NEWLINE")
    self.consume("INDENT")
    steps: list[ast_nodes.AiMemoryPipelineStep] = []
    while not self.check("DEDENT"):
        if self.match("NEWLINE"):
            continue
        if self.check("DASH"):
            steps.append(self._parse_legacy_pipeline_step())
            continue
        steps.append(self._parse_block_pipeline_step())
    self.consume("DEDENT")
    self.optional_newline()
    return steps

def _parse_block_pipeline_step(self) -> ast_nodes.AiMemoryPipelineStep:
    start_tok = self.consume_any({"KEYWORD", "IDENT"})
    if (start_tok.value or "") != "step":
        raise self.error("Expected 'step is \"name\"' inside pipeline.", start_tok)
    self.consume("KEYWORD", "is")
    name_tok = self.consume("STRING")
    step = ast_nodes.AiMemoryPipelineStep(name=(name_tok.value or "").strip(), span=self._span(start_tok))
    self.consume("COLON")
    self.consume("NEWLINE")
    self.consume("INDENT")
    while not self.check("DEDENT"):
        if self.match("NEWLINE"):
            continue
        field_tok = self.consume_any({"KEYWORD", "IDENT"})
        self._assign_pipeline_step_field(step, field_tok)
        self.optional_newline()
    self.consume("DEDENT")
    self._finalize_pipeline_step(step, start_tok)
    return step

def _parse_legacy_pipeline_step(self) -> ast_nodes.AiMemoryPipelineStep:
    self.consume("DASH")
    step = ast_nodes.AiMemoryPipelineStep()
    start_tok = self.peek()
    nested_indent = 0
    while True:
        if nested_indent == 0 and (self.check("DEDENT") or self.check("DASH")):
            break
        if self.match("NEWLINE"):
            continue
        if self.match("INDENT"):
            nested_indent += 1
            continue
        if nested_indent > 0 and self.match("DEDENT"):
            nested_indent -= 1
            continue
        field_tok = self.consume_any({"KEYWORD", "IDENT"})
        self._assign_pipeline_step_field(step, field_tok)
        self.optional_newline()
    self._finalize_pipeline_step(step, start_tok)
    return step

def _assign_pipeline_step_field(
    self,
    step: ast_nodes.AiMemoryPipelineStep,
    field_tok: Token,
) -> None:
    field_name = field_tok.value or ""
    if field_name == "step":
        self.consume("KEYWORD", "is")
        name_tok = self.consume("STRING")
        step.name = (name_tok.value or "").strip()
    elif field_name == "type":
        self.consume("KEYWORD", "is")
        type_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
        step.type = (type_tok.value or "").strip()
    elif field_name == "max_tokens":
        self.consume("KEYWORD", "is")
        num_tok = self.consume("NUMBER")
        step.max_tokens = self._consume_positive_int(
            num_tok, "N3L-1202: max_tokens must be a positive integer."
        )
    elif field_name == "target_kind":
        self.consume("KEYWORD", "is")
        target_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
        step.target_kind = (target_tok.value or "").strip()
    elif field_name == "embedding_model":
        self.consume("KEYWORD", "is")
        embed_tok = self.consume("STRING")
        step.embedding_model = (embed_tok.value or "").strip()
    else:
        raise self.error(f"Unexpected field '{field_name}' in memory pipeline step.", field_tok)

def _finalize_pipeline_step(
    self,
    step: ast_nodes.AiMemoryPipelineStep,
    start_tok: Token,
) -> None:
    if not (step.name or "").strip():
        raise self.error("Memory pipeline step requires a non-empty 'step' name.", start_tok)
    if not (step.type or "").strip():
        raise self.error("Memory pipeline step requires a 'type'.", start_tok)
    step.span = self._span(start_tok)

def _consume_positive_int(self, token: Token, error_msg: str) -> int:
    try:
        value = int(token.value or "0")
    except Exception:
        value = 0
    if value <= 0:
        raise self.error(error_msg, token)
    return value

def _consume_bool_literal(self, token: Token, error_msg: str) -> bool:
    literal = (token.value or "").lower()
    if literal not in {"true", "false"}:
        raise self.error(error_msg, token)
    return literal == "true"

