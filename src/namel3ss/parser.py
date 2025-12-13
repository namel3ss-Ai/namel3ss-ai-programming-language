"""
Parser for the minimal Namel3ss V3 language slice.
"""

from __future__ import annotations

from typing import List, Set
from difflib import get_close_matches

from . import ast_nodes
from .errors import ParseError
from .lexer import Lexer, Token
from .parser import expr
from .parser.stmt import core as stmt_core
from .parser.stmt import blocks as stmt_blocks
from .parser.stmt.decl_ai import core as decl_ai_core
from .parser.stmt.decl_ai import memory as decl_ai_memory
from .parser.stmt.decl_ai import memory_kinds as decl_ai_memory_kinds
from .parser.stmt.decl_ai import memory_pipeline as decl_ai_memory_pipeline
from .parser.stmt.declarations import (
    agent as decl_agent,
    app as decl_app,
    common as decl_common,
    flow as decl_flow,
    graph as decl_graph,
    macro as decl_macro,
    memory as decl_memory,
    model as decl_model,
    page as decl_page,
    rag as decl_rag,
    record as decl_record,
    storage as decl_storage,
    tool as decl_tool,
    ui as decl_ui,
)
from .parser.stmt.conditions import conditions as stmt_conditions
from .parser.stmt.conditions import patterns as stmt_patterns
from .parser import validator as stmt_validation


class Parser:
    def __init__(self, tokens: List[Token]) -> None:
        self.tokens = tokens
        self.position = 0
        self._ai_field_candidates = {
            "model",
            "provider",
            "system",
            "system_prompt",
            "input",
            "when",
            "describe",
            "description",
            "memory",
            "use",
            "tools",
        }
        self._transaction_depth = 0

    @classmethod
    def from_source(cls, source: str) -> "Parser":
        return cls(Lexer(source).tokenize())

    def parse_module(self) -> ast_nodes.Module:
        module = ast_nodes.Module()
        while not self.check("EOF"):
            if self.match("NEWLINE"):
                continue
            if (
                self.position > 0
                and self.tokens[self.position - 1].type == "STRING"
                and self.tokens[self.position - 1].line == self.peek().line
                and self.peek().type == "KEYWORD"
            ):
                raise self.error(
                    f"N3L-PARSE-NEWLINE: Top-level blocks must start on a new line. Did you forget a newline before '{self.peek().value}'?",
                    self.peek(),
                )
            module.declarations.append(self.parse_declaration())
        return module

    def parse_declaration(self) -> ast_nodes.Declaration:
        token = self.peek()
        if token.type != "KEYWORD":
            raise self.error("Expected a declaration", token)

        if token.value == "remember":
            return self.parse_english_memory()
        if token.value == "use" and self.peek_offset(1).value == "model":
            return self.parse_english_model()
        if token.value == "use":
            return self.parse_use()
        if token.value == "from":
            return self.parse_from_import()
        if token.value == "define" and self.peek_offset(1).value == "condition":
            return self.parse_condition_macro()
        if token.value == "define" and self.peek_offset(1).value == "rulegroup":
            return self.parse_rulegroup()
        if token.value == "define" and self.peek_offset(1).value == "helper":
            return self.parse_helper()
        if token.value == "app":
            return self.parse_app()
        if token.value == "page":
            return self.parse_page()
        if token.value == "model":
            return self.parse_model()
        if token.value == "ai":
            return self.parse_ai()
        if token.value == "agent":
            if self.peek_offset(1).value == "evaluation":
                return self.parse_agent_evaluation()
            return self.parse_agent()
        if token.value == "memory":
            if (self.peek_offset(1).value or "") == "profile":
                return self.parse_memory_profile()
            return self.parse_memory()
        if token.value == "record":
            return self.parse_record()
        if token.value == "auth":
            return self.parse_auth()
        if token.value == "frame":
            return self.parse_frame()
        if token.value == "vector_store":
            return self.parse_vector_store()
        if token.value == "graph":
            return self.parse_graph()
        if token.value == "graph_summary":
            return self.parse_graph_summary()
        if token.value == "tool":
            if (self.peek_offset(1).value or "") == "evaluation":
                return self.parse_tool_evaluation()
            return self.parse_tool()
        if token.value == "rag":
            next_tok = self.peek_offset(1)
            if next_tok.value == "pipeline":
                return self.parse_rag_pipeline()
            if next_tok.value == "evaluation":
                return self.parse_rag_evaluation()
            raise self.error("Expected 'pipeline' or 'evaluation' after 'rag'.", next_tok)
        if token.value == "macro":
            next_tok = self.peek_offset(1)
            if next_tok.value == "test":
                return self.parse_macro_test()
            return self.parse_macro()
        if token.value == "flow":
            return self.parse_flow()
        if token.value == "plugin":
            return self.parse_plugin()
        if token.value == "settings":
            return self.parse_settings()
        if token.value == "component":
            return self.parse_ui_component_decl()
        if token.value in {"heading", "text", "image"}:
            raise self.error("N3U-1300: layout element outside of a page or section", token)
        if token.value == "state":
            raise self.error("N3U-2000: state declared outside a page", token)
        if token.value == "input":
            raise self.error("N3U-2100: input outside of a page or section", token)
        if token.value == "button":
            raise self.error("N3U-2200: button outside of a page or section", token)
        if token.value in {"when", "otherwise", "show"}:
            raise self.error("N3U-2300: conditional outside of a page or section", token)
        if token.value == "table":
            raise self.error('Use frame is "name": with a table: block instead of top-level table declarations.', token)
        raise self.error(f"Unexpected declaration '{token.value}'", token)

    parse_condition_macro = decl_macro.parse_condition_macro
    parse_rulegroup = decl_macro.parse_rulegroup
    parse_helper = decl_macro.parse_helper
    parse_macro = decl_macro.parse_macro
    parse_macro_test = decl_macro.parse_macro_test
    parse_macro_use = decl_macro.parse_macro_use
    _parse_macro_fields_block = decl_macro._parse_macro_fields_block
    parse_use = decl_common.parse_use
    parse_from_import = decl_common.parse_from_import
    parse_english_memory = decl_common.parse_english_memory
    parse_english_model = decl_common.parse_english_model
    parse_auth = decl_common.parse_auth
    parse_plugin = decl_common.parse_plugin
    parse_settings = decl_common.parse_settings
    _parse_string_list_literal = decl_common._parse_string_list_literal
    parse_app = decl_app.parse_app
    parse_page = decl_page.parse_page
    parse_model = decl_model.parse_model
    parse_agent = decl_agent.parse_agent
    parse_agent_evaluation = decl_agent.parse_agent_evaluation
    parse_memory = decl_memory.parse_memory
    parse_memory_profile = decl_memory.parse_memory_profile
    parse_record = decl_record.parse_record
    parse_ui_component_decl = decl_ui.parse_ui_component_decl
    _is_style_token = decl_ui._is_style_token
    _parse_style_block = decl_ui._parse_style_block
    parse_style_line = decl_ui.parse_style_line
    parse_style_map_block = decl_ui.parse_style_map_block
    _parse_class_value = decl_ui._parse_class_value
    parse_layout_block = decl_ui.parse_layout_block
    parse_layout_section = decl_ui.parse_layout_section
    parse_card = decl_ui.parse_card
    parse_row = decl_ui.parse_row
    parse_column = decl_ui.parse_column
    parse_message_list = decl_ui.parse_message_list
    parse_message = decl_ui.parse_message
    parse_component_call = decl_ui.parse_component_call
    parse_button = decl_ui.parse_button
    _parse_navigate_action = decl_ui._parse_navigate_action
    parse_ui_conditional = decl_ui.parse_ui_conditional
    parse_section = decl_ui.parse_section
    parse_component = decl_ui.parse_component
    parse_english_component = decl_ui.parse_english_component
    parse_tool = decl_tool.parse_tool
    parse_tool_evaluation = decl_tool.parse_tool_evaluation
    _parse_tool_retry_block = decl_tool._parse_tool_retry_block
    _parse_retry_block = decl_tool._parse_retry_block
    _parse_tool_auth_block = decl_tool._parse_tool_auth_block
    _parse_auth_block = decl_tool._parse_auth_block
    _parse_tool_rate_limit_block = decl_tool._parse_tool_rate_limit_block
    _parse_rate_limit_block = decl_tool._parse_rate_limit_block
    _parse_response_schema = decl_tool._parse_response_schema
    parse_rag_evaluation = decl_rag.parse_rag_evaluation
    parse_rag_pipeline = decl_rag.parse_rag_pipeline
    _parse_rag_stage = decl_rag._parse_rag_stage
    parse_vector_store = decl_storage.parse_vector_store
    parse_frame = decl_storage.parse_frame
    parse_graph = decl_graph.parse_graph
    parse_graph_summary = decl_graph.parse_graph_summary
    parse_ai = decl_ai_core.parse_ai
    parse_ai_called_block = decl_ai_core.parse_ai_called_block
    _parse_ai_tools_block = decl_ai_core._parse_ai_tools_block
    _parse_ai_tool_binding_entry = decl_ai_core._parse_ai_tool_binding_entry
    _parse_memory_block = decl_ai_memory._parse_memory_block
    _suggest_memory_kind = decl_ai_memory._suggest_memory_kind
    _parse_memory_kinds_block = decl_ai_memory_kinds._parse_memory_kinds_block
    _parse_short_term_kind = decl_ai_memory_kinds._parse_short_term_kind
    _parse_long_term_kind = decl_ai_memory_kinds._parse_long_term_kind
    _parse_profile_kind = decl_ai_memory_kinds._parse_profile_kind
    _parse_episodic_kind = decl_ai_memory_kinds._parse_episodic_kind
    _parse_semantic_kind = decl_ai_memory_kinds._parse_semantic_kind
    _parse_time_decay_block = decl_ai_memory_kinds._parse_time_decay_block
    _parse_memory_recall_block = decl_ai_memory_pipeline._parse_memory_recall_block
    _parse_memory_pipeline_block = decl_ai_memory_pipeline._parse_memory_pipeline_block
    _parse_block_pipeline_step = decl_ai_memory_pipeline._parse_block_pipeline_step
    _parse_legacy_pipeline_step = decl_ai_memory_pipeline._parse_legacy_pipeline_step
    _assign_pipeline_step_field = decl_ai_memory_pipeline._assign_pipeline_step_field
    _finalize_pipeline_step = decl_ai_memory_pipeline._finalize_pipeline_step
    _consume_positive_int = decl_ai_memory_pipeline._consume_positive_int
    _consume_bool_literal = decl_ai_memory_pipeline._consume_bool_literal
    parse_statement_or_action = stmt_core.parse_statement_or_action
    parse_statement_block = stmt_core.parse_statement_block
    parse_if_statement = stmt_core.parse_if_statement
    parse_match_statement = stmt_core.parse_match_statement
    parse_guard_statement = stmt_core.parse_guard_statement
    parse_try_catch_statement = stmt_core.parse_try_catch_statement
    _parse_destructuring_pattern = stmt_core._parse_destructuring_pattern
    _split_field_access_expr = stmt_core._split_field_access_expr
    parse_let_statement = stmt_core.parse_let_statement
    parse_collection_pipeline_steps = stmt_core.parse_collection_pipeline_steps
    parse_set_statement = stmt_core.parse_set_statement
    parse_repeat_statement = stmt_core.parse_repeat_statement
    parse_retry_statement = stmt_core.parse_retry_statement
    parse_ask_statement = stmt_blocks.parse_ask_statement
    parse_form_statement = stmt_blocks.parse_form_statement
    parse_log_statement = stmt_blocks.parse_log_statement
    parse_note_statement = stmt_blocks.parse_note_statement
    parse_checkpoint_statement = stmt_blocks.parse_checkpoint_statement
    parse_return_statement = stmt_blocks.parse_return_statement
    _parse_do_action = stmt_blocks._parse_do_action
    parse_do_actions = stmt_blocks.parse_do_actions
    parse_goto_action = stmt_blocks.parse_goto_action
    parse_conditional_into = stmt_blocks.parse_conditional_into
    _parse_optional_binding = stmt_blocks._parse_optional_binding
    _parse_validation_block = stmt_validation._parse_validation_block
    parse_condition_expr = stmt_patterns.parse_condition_expr
    parse_pattern_expr = stmt_patterns.parse_pattern_expr
    _parse_where_conditions = stmt_conditions._parse_where_conditions
    _combine_conditions = stmt_conditions._combine_conditions
    _parse_condition_expr = stmt_conditions._parse_condition_expr
    _parse_condition_and = stmt_conditions._parse_condition_and
    _parse_condition_primary = stmt_conditions._parse_condition_primary
    _expr_to_condition = stmt_conditions._expr_to_condition
    _parse_duration_value = stmt_conditions._parse_duration_value
    _parse_step_body = decl_flow._parse_step_body
    _build_flow_step_decl = decl_flow._build_flow_step_decl
    parse_flow_step = decl_flow.parse_flow_step
    parse_flow = decl_flow.parse_flow_decl

    parse_expression = expr.parse_expression
    parse_or = expr.parse_or
    parse_and = expr.parse_and
    parse_not = expr.parse_not
    parse_comparison = expr.parse_comparison
    parse_add = expr.parse_add
    parse_mul = expr.parse_mul
    parse_unary = expr.parse_unary
    parse_primary = expr.parse_primary
    parse_postfix = expr.parse_postfix
    parse_list_literal = expr.parse_list_literal
    parse_record_literal = expr.parse_record_literal
    parse_english_builtin = expr.parse_english_builtin
    parse_english_all = expr.parse_english_all
    parse_english_any = expr.parse_english_any
    parse_builtin_call = expr.parse_builtin_call
    parse_function_call = expr.parse_function_call

    def optional_newline(self) -> None:
        if self.check("NEWLINE"):
            self.advance()

    def consume_string_value(self, field_token: Token, field_name: str) -> Token:
        if not self.check("STRING"):
            raise self.error(f"Expected string after '{field_name}'", self.peek())
        return self.consume("STRING")

    def consume(self, token_type: str, value: str | None = None) -> Token:
        token = self.peek()
        if token.type != token_type:
            raise self.error(f"Expected {token_type}", token)
        if value is not None and token.value != value:
            raise self.error(f"Expected '{value}'", token)
        self.advance()
        return token

    def consume_any(self, token_types: set[str]) -> Token:
        token = self.peek()
        if token.type not in token_types:
            raise self.error(f"Expected one of {token_types}", token)
        self.advance()
        return token

    def match(self, token_type: str) -> bool:
        if self.check(token_type):
            self.advance()
            return True
        return False

    def match_value(self, token_type: str, value: str) -> bool:
        if self.check(token_type) and self.peek().value == value:
            self.advance()
            return True
        return False

    def check(self, token_type: str) -> bool:
        return self.peek().type == token_type

    def peek(self) -> Token:
        return self.tokens[self.position]

    def peek_offset(self, offset: int) -> Token:
        idx = min(self.position + offset, len(self.tokens) - 1)
        return self.tokens[idx]

    def advance(self) -> Token:
        token = self.tokens[self.position]
        self.position = min(self.position + 1, len(self.tokens) - 1)
        return token

    def error(self, message: str, token: Token) -> ParseError:
        return ParseError(message, token.line, token.column)

    def _span(self, token: Token) -> ast_nodes.Span:
        return ast_nodes.Span(line=token.line, column=token.column)


def parse_source(source: str) -> ast_nodes.Module:
    """Parse helper for tests and tooling."""
    return Parser.from_source(source).parse_module()
