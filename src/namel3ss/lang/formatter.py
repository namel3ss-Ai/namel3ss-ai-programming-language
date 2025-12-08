"""Source formatter for Namel3ss .ai programs."""

from __future__ import annotations

from typing import List

from .. import ast_nodes
from ..errors import ParseError
from ..parser import parse_source

INDENT = "  "


def _q(value: str) -> str:
    return f"\"{value.replace('\"', '\\\"')}\""


def _indent(level: int, text: str) -> str:
    return f"{INDENT * level}{text}"


def format_source(source: str, *, filename: str | None = None) -> str:
    """
    Parse the given Namel3ss source and return formatted code.
    Raises ParseError on invalid input.
    """
    try:
        module = parse_source(source)
    except ParseError:
        raise
    formatted = _format_module(module)
    if not formatted.endswith("\n"):
        formatted += "\n"
    return formatted


def _format_module(module: ast_nodes.Module) -> str:
    lines: List[str] = []
    for idx, decl in enumerate(module.declarations):
        lines.extend(_format_decl(decl, 0))
        if idx != len(module.declarations) - 1:
            lines.append("")
    return "\n".join(lines)


def _format_decl(decl: ast_nodes.Declaration, level: int) -> List[str]:
    if isinstance(decl, ast_nodes.UseImport):
        return [_indent(level, f"use {_q(decl.path)}")]
    if isinstance(decl, ast_nodes.AppDecl):
        body: List[str] = []
        if decl.entry_page:
            body.append(_indent(level + 1, f"entry_page {_q(decl.entry_page)}"))
        if decl.description:
            body.append(_indent(level + 1, f"description {_q(decl.description)}"))
        return [_indent(level, f"app {_q(decl.name)}:")] + body
    if isinstance(decl, ast_nodes.PageDecl):
        body: List[str] = []
        if decl.route:
            body.append(_indent(level + 1, f"route {_q(decl.route)}"))
        if decl.title:
            body.append(_indent(level + 1, f"title {_q(decl.title)}"))
        if decl.description:
            body.append(_indent(level + 1, f"description {_q(decl.description)}"))
        skip_keys = {"route", "title", "description"}
        for prop in decl.properties:
            if prop.key in skip_keys:
                continue
            body.append(_indent(level + 1, f"{prop.key} {_q(prop.value)}"))
        for ai_ref in decl.ai_calls:
            body.append(_indent(level + 1, f"ai {_q(ai_ref.name)}"))
        for agent_ref in decl.agents:
            body.append(_indent(level + 1, f"agent {_q(agent_ref.name)}"))
        for mem_ref in decl.memories:
            body.append(_indent(level + 1, f"memory {_q(mem_ref.name)}"))
        for section in decl.sections:
            body.extend(_format_section(section, level + 1))
        return [_indent(level, f"page {_q(decl.name)}:")] + body
    if isinstance(decl, ast_nodes.ModelDecl):
        body: List[str] = []
        if decl.provider:
            body.append(_indent(level + 1, f"provider {_q(decl.provider)}"))
        return [_indent(level, f"model {_q(decl.name)}:")] + body
    if isinstance(decl, ast_nodes.AICallDecl):
        body: List[str] = []
        if decl.model_name:
            body.append(_indent(level + 1, f"model {_q(decl.model_name)}"))
        if getattr(decl, "provider", None):
            body.append(_indent(level + 1, f"provider {_q(decl.provider or '')}"))
        if getattr(decl, "system_prompt", None):
            body.append(_indent(level + 1, f"system {_q(decl.system_prompt or '')}"))
        if decl.input_source:
            body.append(_indent(level + 1, f"input from {_q(decl.input_source)}"))
        if getattr(decl, "description", None):
            body.append(_indent(level + 1, f"description {_q(decl.description or '')}"))
        return [_indent(level, f"ai {_q(decl.name)}:")] + body
    if isinstance(decl, ast_nodes.AgentDecl):
        body: List[str] = []
        if decl.goal:
            body.append(_indent(level + 1, f"goal {_q(decl.goal)}"))
        if decl.personality:
            body.append(_indent(level + 1, f"personality {_q(decl.personality)}"))
        if getattr(decl, "system_prompt", None):
            body.append(_indent(level + 1, f"system {_q(decl.system_prompt or '')}"))
        return [_indent(level, f"agent {_q(decl.name)}:")] + body
    if isinstance(decl, ast_nodes.MemoryDecl):
        body: List[str] = []
        if decl.memory_type:
            body.append(_indent(level + 1, f"type {_q(decl.memory_type)}"))
        return [_indent(level, f"memory {_q(decl.name)}:")] + body
    if isinstance(decl, ast_nodes.PluginDecl):
        if decl.description:
            return [
                _indent(level, f"plugin {_q(decl.name)}:"),
                _indent(level + 1, f"description {_q(decl.description)}"),
            ]
        return [_indent(level, f"plugin {_q(decl.name)}")]
    if isinstance(decl, ast_nodes.FlowDecl):
        body: List[str] = []
        if decl.description:
            body.append(_indent(level + 1, f"description {_q(decl.description)}"))
        for step in decl.steps:
            body.extend(_format_flow_step(step, level + 1))
        return [_indent(level, f"flow {_q(decl.name)}:")] + body
    raise ValueError(f"Unknown declaration type: {type(decl)}")


def _format_section(section: ast_nodes.SectionDecl, level: int) -> List[str]:
    lines = [_indent(level, f"section {_q(section.name)}:")]
    for comp in section.components:
        lines.extend(_format_component(comp, level + 1))
    return lines


def _format_component(comp: ast_nodes.ComponentDecl, level: int) -> List[str]:
    lines = [_indent(level, f"component {_q(comp.type)}:")]
    for prop in comp.props:
        lines.append(_indent(level + 1, f"{prop.key} {_q(prop.value)}"))
    return lines


def _format_flow_step(step: ast_nodes.FlowStepDecl, level: int) -> List[str]:
    lines = [_indent(level, f"step {_q(step.name)}:")]
    lines.append(_indent(level + 1, f"kind {_q(step.kind)}"))
    lines.append(_indent(level + 1, f"target {_q(step.target)}"))
    if getattr(step, "message", None):
        lines.append(_indent(level + 1, f"message {_q(step.message or '')}"))
    return lines
