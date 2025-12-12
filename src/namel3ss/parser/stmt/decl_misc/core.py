"""Parsing helpers for imports, English helpers, auth, plugins, and settings."""

from __future__ import annotations

from typing import Set

from .... import ast_nodes

__all__ = [
    "parse_use",
    "parse_from_import",
    "parse_english_memory",
    "parse_english_model",
    "parse_auth",
    "parse_plugin",
    "parse_settings",
    "_parse_string_list_literal",
]


def parse_use(self) -> ast_nodes.UseImport:
    start = self.consume("KEYWORD", "use")
    if self.peek().value == "macro":
        return self.parse_macro_use(start)
    if self.peek().value == "module":
        self.consume("KEYWORD", "module")
        mod = self.consume("STRING")
        self.optional_newline()
        return ast_nodes.ModuleUse(module=mod.value or "", span=self._span(start))
    path = self.consume("STRING")
    self.optional_newline()
    return ast_nodes.UseImport(path=path.value or "", span=self._span(start))


def parse_from_import(self) -> ast_nodes.ImportDecl:
    start = self.consume("KEYWORD", "from")
    module_tok = self.consume("STRING")
    self.consume("KEYWORD", "use")
    kind_tok = self.consume_any({"IDENT", "KEYWORD"})
    if kind_tok.value not in {"helper", "flow", "agent"}:
        raise self.error("Expected helper/flow/agent after 'use'", kind_tok)
    name_tok = self.consume("STRING")
    self.optional_newline()
    return ast_nodes.ImportDecl(module=module_tok.value or "", kind=kind_tok.value or "", name=name_tok.value or "", span=self._span(start))


def parse_english_memory(self) -> ast_nodes.MemoryDecl:
    start = self.consume("KEYWORD", "remember")
    self.consume("KEYWORD", "conversation")
    self.consume("KEYWORD", "as")
    name = self.consume("STRING")
    self.optional_newline()
    return ast_nodes.MemoryDecl(
        name=name.value or "",
        memory_type="conversation",
        span=self._span(start),
    )


def parse_english_model(self) -> ast_nodes.ModelDecl:
    start = self.consume("KEYWORD", "use")
    self.consume("KEYWORD", "model")
    name = self.consume("STRING")
    self.consume("KEYWORD", "provided")
    self.consume("KEYWORD", "by")
    provider = self.consume("STRING")
    self.optional_newline()
    return ast_nodes.ModelDecl(
        name=name.value or "",
        provider=provider.value,
        span=self._span(start),
    )


def parse_auth(self) -> ast_nodes.AuthDecl:
    start = self.consume("KEYWORD", "auth")
    if self.match_value("KEYWORD", "is"):
        pass
    self.consume("COLON")
    self.consume("NEWLINE")
    self.consume("INDENT")

    backend = None
    user_record = None
    id_field = None
    identifier_field = None
    password_hash_field = None
    allowed_fields = {"backend", "user_record", "id_field", "identifier_field", "password_hash_field"}
    while not self.check("DEDENT"):
        if self.match("NEWLINE"):
            continue
        field_token = self.consume("KEYWORD")
        if field_token.value not in allowed_fields:
            raise self.error(
                f"Unexpected field '{field_token.value}' in auth block",
                field_token,
            )
        if self.match_value("KEYWORD", "is"):
            value_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
        else:
            value_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
        value = value_tok.value or ""
        if field_token.value == "backend":
            backend = value
        elif field_token.value == "user_record":
            user_record = value
        elif field_token.value == "id_field":
            id_field = value
        elif field_token.value == "identifier_field":
            identifier_field = value
        elif field_token.value == "password_hash_field":
            password_hash_field = value
        self.optional_newline()
    self.consume("DEDENT")
    self.optional_newline()
    return ast_nodes.AuthDecl(
        backend=backend,
        user_record=user_record,
        id_field=id_field,
        identifier_field=identifier_field,
        password_hash_field=password_hash_field,
        span=self._span(start),
    )


def parse_plugin(self) -> ast_nodes.PluginDecl:
    start = self.consume("KEYWORD", "plugin")
    if self.match_value("KEYWORD", "is"):
        name = self.consume("STRING")
    else:
        tok = self.peek()
        if tok.type == "STRING":
            raise self.error(f'plugin "{tok.value}": is not supported. Use plugin is "{tok.value}": instead.', tok)
        raise self.error("Expected 'is' after 'plugin'", tok)
    description = None
    if self.check("COLON"):
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")
        while not self.check("DEDENT"):
            field_token = self.consume("KEYWORD")
            if field_token.value != "description":
                raise self.error(
                    f"Unexpected field '{field_token.value}' in plugin block",
                    field_token,
                )
            desc_token = self.consume_string_value(field_token, "description")
            description = desc_token.value
            self.optional_newline()
        self.consume("DEDENT")
        self.optional_newline()
    else:
        self.optional_newline()
    return ast_nodes.PluginDecl(
        name=name.value or "", description=description, span=self._span(start)
    )


def parse_settings(self) -> ast_nodes.SettingsDecl:
    start = self.consume("KEYWORD", "settings")
    self.consume("COLON")
    self.consume("NEWLINE")
    self.consume("INDENT")
    envs: list[ast_nodes.EnvConfig] = []
    seen_envs: set[str] = set()
    theme_entries: list[ast_nodes.ThemeEntry] = []
    seen_theme: set[str] = set()
    while not self.check("DEDENT"):
        if self.match("NEWLINE"):
            continue
        if self.peek().value == "theme":
            self.consume("KEYWORD", "theme")
            self.consume("COLON")
            self.consume("NEWLINE")
            self.consume("INDENT")
            while not self.check("DEDENT"):
                if self.match("NEWLINE"):
                    continue
                key_tok = self.consume_any({"IDENT", "KEYWORD"})
                if self.peek().value != "color":
                    raise self.error("N3U-3001: invalid color literal", self.peek())
                self.consume("KEYWORD", "color")
                self.consume("KEYWORD", "be")
                if not self.check("STRING"):
                    raise self.error("N3U-3001: invalid color literal", self.peek())
                val_tok = self.consume("STRING")
                key = key_tok.value or ""
                if key in seen_theme:
                    raise self.error("N3U-3002: duplicate theme key", key_tok)
                seen_theme.add(key)
                theme_entries.append(ast_nodes.ThemeEntry(key=key, value=val_tok.value or "", span=self._span(val_tok)))
                self.optional_newline()
            self.consume("DEDENT")
            self.optional_newline()
            continue
        self.consume("KEYWORD", "env")
        env_name_tok = self.consume("STRING")
        env_name = env_name_tok.value or ""
        if env_name in seen_envs:
            raise self.error("N3-6200: duplicate env definition", env_name_tok)
        seen_envs.add(env_name)
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")
        entries: list[ast_nodes.SettingEntry] = []
        seen_keys: set[str] = set()
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            key_tok = self.consume_any({"IDENT", "KEYWORD"})
            if key_tok.value in seen_keys:
                raise self.error("N3-6201: duplicate key inside env", key_tok)
            seen_keys.add(key_tok.value or "")
            if not self.match_value("KEYWORD", "be"):
                raise self.error("Expected 'be' in env entry", self.peek())
            expr = self.parse_expression()
            entries.append(ast_nodes.SettingEntry(key=key_tok.value or "", expr=expr))
            self.optional_newline()
        self.consume("DEDENT")
        self.optional_newline()
        envs.append(ast_nodes.EnvConfig(name=env_name, entries=entries, span=self._span(env_name_tok)))
    self.consume("DEDENT")
    self.optional_newline()
    return ast_nodes.SettingsDecl(envs=envs, theme=theme_entries, span=self._span(start))


def _parse_string_list_literal(self, start_token) -> list[str]:
    lit = self.parse_list_literal()
    values: list[str] = []
    for item in lit.items:
        if isinstance(item, ast_nodes.Literal) and isinstance(item.value, str):
            values.append(item.value)
        elif isinstance(item, ast_nodes.Identifier):
            values.append(item.name)
        else:
            raise self.error("Columns must be specified as a list of strings.", start_token)
    return values
