from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, List

from . import ast_nodes
from .diagnostics.registry import create_diagnostic
from . import lexer
from .errors import Namel3ssError
from .linting import lint_module
from .parser import parse_source
from .runtime.expressions import ExpressionEvaluator, VariableEnvironment


class MacroExpansionError(Namel3ssError):
    pass


MacroCallback = Callable[[ast_nodes.MacroDecl, Dict[str, Any]], str]


class MacroExpander:
    def __init__(self, ai_callback: MacroCallback) -> None:
        self.ai_callback = ai_callback
        self._stack: list[str] = []
        self._builtin_macros = _builtin_macros()

    def expand_module(self, module: ast_nodes.Module) -> ast_nodes.Module:
        macro_registry: dict[str, ast_nodes.MacroDecl] = {m.name: m for m in self._builtin_macros}
        for decl in module.declarations:
            if isinstance(decl, ast_nodes.MacroDecl):
                if decl.name in macro_registry:
                    raise MacroExpansionError(create_diagnostic("N3M-1001", message_kwargs={"name": decl.name}).message)
                macro_registry[decl.name] = decl

        new_decls: list[ast_nodes.Declaration] = []
        existing_names: dict[tuple[type, str], ast_nodes.Declaration] = {}

        def register_decl(d: ast_nodes.Declaration):
            name = getattr(d, "name", None)
            key = (type(d), name)
            if name and key in existing_names:
                raise MacroExpansionError(create_diagnostic("N3M-1203", message_kwargs={"name": name}).message)
            existing_names[key] = d
            new_decls.append(d)

        for decl in module.declarations:
            if isinstance(decl, ast_nodes.MacroUse):
                expanded = self._expand_use(decl, macro_registry)
                for d in expanded.declarations:
                    if isinstance(d, (ast_nodes.MacroDecl, ast_nodes.MacroUse)):
                        continue
                    register_decl(d)
            elif isinstance(decl, ast_nodes.MacroDecl):
                continue
            else:
                register_decl(decl)
        return ast_nodes.Module(declarations=new_decls)

    def _expand_use(self, use: ast_nodes.MacroUse, registry: Dict[str, ast_nodes.MacroDecl]) -> ast_nodes.Module:
        if use.macro_name not in registry:
            raise MacroExpansionError(create_diagnostic("N3M-1100", message_kwargs={"name": use.macro_name}).message)
        if use.macro_name in self._stack:
            raise MacroExpansionError(create_diagnostic("N3M-1302", message_kwargs={"name": use.macro_name}).message)
        macro = registry[use.macro_name]
        args = self._evaluate_args(macro, use.args)
        payload = {
            "description": macro.description,
            "sample": macro.sample,
            "parameters": macro.parameters,
            "args": args,
            "instruction": "Return ONLY valid Namel3ss code. No explanations.",
        }
        prompt = json.dumps(payload)
        if macro.name == "crud_ui":
            output = self._generate_crud_ui(args)
        else:
            output = self.ai_callback(macro, args)
        if not output or not isinstance(output, str):
            raise MacroExpansionError(create_diagnostic("N3M-1102", message_kwargs={"name": use.macro_name}).message)
        if len(output) > 2000:
            raise MacroExpansionError(create_diagnostic("N3M-1300", message_kwargs={"name": use.macro_name}).message)
        if "```" in output or "`" in output:
            raise MacroExpansionError(create_diagnostic("N3M-1301", message_kwargs={"name": use.macro_name}).message)
        self._stack.append(use.macro_name)
        try:
            generated_module = self._parse_generated(output)
            if any(isinstance(d, ast_nodes.MacroUse) and d.macro_name == use.macro_name for d in generated_module.declarations):
                raise MacroExpansionError(create_diagnostic("N3M-1302", message_kwargs={"name": use.macro_name}).message)
            findings = lint_module(generated_module)
            if findings:
                raise MacroExpansionError(create_diagnostic("N3M-1202", message_kwargs={"name": use.macro_name}).message)
            if not generated_module.declarations:
                raise MacroExpansionError(create_diagnostic("N3M-1103", message_kwargs={"name": use.macro_name}).message)
            return generated_module
        finally:
            self._stack.pop()

    def _parse_generated(self, source: str) -> ast_nodes.Module:
        try:
            return parse_source(source)
        except Exception as exc:
            raise MacroExpansionError(create_diagnostic("N3M-1201", message_kwargs={"detail": str(exc)}).message)

    def _evaluate_args(self, macro: ast_nodes.MacroDecl, args: Dict[str, ast_nodes.Expr]) -> Dict[str, Any]:
        env = VariableEnvironment()
        evaluator = ExpressionEvaluator(env, resolver=lambda name: (False, None))
        evaluated: dict[str, Any] = {}
        if macro.parameters:
            for param in macro.parameters:
                if param not in args:
                    raise MacroExpansionError(create_diagnostic("N3M-1101", message_kwargs={"name": param}).message)
        try:
            for key, expr in args.items():
                evaluated[key] = evaluator.evaluate(expr)
            return evaluated
        except Exception as exc:
            raise MacroExpansionError(create_diagnostic("N3M-1101", message_kwargs={"name": key}).message) from exc

    def _generate_crud_ui(self, args: Dict[str, Any]) -> str:
        entity = args.get("entity")
        fields = args.get("fields")
        if not isinstance(entity, str) or not entity.strip():
            raise MacroExpansionError(create_diagnostic("N3M-5000").message)
        if not isinstance(fields, list) or not all(isinstance(f, str) and f.strip() for f in fields):
            raise MacroExpansionError(create_diagnostic("N3M-5001").message)
        entity = entity.strip()
        slug = entity.lower()
        plural = f"{slug}s"
        cap_fields = []
        for raw in fields:
            ident = _sanitize_identifier(raw)
            label = raw.strip().replace("_", " ").title()
            cap_fields.append((ident, label))
        form_name = f"{entity} Form"
        form_var = f"{slug}_form"

        lines: list[str] = []

        # Flows
        flow_names = [
            f"list_{plural}",
            f"create_{slug}",
            f"update_{slug}",
            f"delete_{slug}",
            f"get_{slug}",
        ]
        for flow_name in flow_names:
            lines.append(f'flow "{flow_name}":')
            lines.append('  step "start":')
            lines.append(f'    log info "{flow_name} step"')
            lines.append("")

        # Pages
        lines.append(f'page "{plural}_list" at "/{plural}":')
        lines.append("  layout is column")
        lines.append("  padding is medium")
        lines.append(f'  heading "{entity} List"')
        lines.append("    color is primary")
        lines.append(f'  text "Browse all {entity}s"')
        lines.append(f'  button "Create {entity}":')
        lines.append("    on click:")
        lines.append(f'      go to page "create_{slug}"')
        lines.append("")

        # Create page
        lines.append(f'page "create_{slug}" at "/{plural}/create":')
        lines.append("  layout is column")
        lines.append("  padding is medium")
        lines.append(f'  heading "Create {entity}"')
        lines.append("    color is primary")
        for field_id, label in cap_fields:
            lines.append(f'  state {field_id} is ""')
        for field_id, label in cap_fields:
            lines.append(f'  input "{label}" as {field_id}')
        lines.append(f'  button "Create {entity}":')
        lines.append("    on click:")
        field_pairs = ", ".join([f"{fid}: {fid}" for fid, _ in cap_fields])
        lines.append(f'      do flow "create_{slug}" with {field_pairs}')
        lines.append(f'      go to page "{plural}_list"')
        lines.append("")

        # Edit page
        lines.append(f'page "edit_{slug}" at "/{plural}/edit":')
        lines.append("  layout is column")
        lines.append("  padding is medium")
        lines.append(f'  heading "Edit {entity}"')
        lines.append("    color is primary")
        lines.append('  state id is ""')
        for field_id, label in cap_fields:
            lines.append(f'  state {field_id} is ""')
        for field_id, label in cap_fields:
            lines.append(f'  input "{label}" as {field_id}')
        lines.append(f'  button "Update {entity}":')
        lines.append("    on click:")
        update_pairs = ", ".join([f"{fid}: {fid}" for fid, _ in cap_fields] + ["id: id"])
        lines.append(f'      do flow "update_{slug}" with {update_pairs}')
        lines.append(f'      go to page "{plural}_list"')
        lines.append("")

        # Detail page
        lines.append(f'page "{slug}_detail" at "/{plural}/detail":')
        lines.append("  layout is column")
        lines.append("  padding is medium")
        lines.append(f'  heading "{entity} Detail"')
        lines.append("    color is primary")
        lines.append('  text "Detail view"')
        lines.append(f'  button "Back to list":')
        lines.append("    on click:")
        lines.append(f'      go to page "{plural}_list"')
        lines.append("")

        # Delete confirm page
        lines.append(f'page "delete_{slug}" at "/{plural}/delete":')
        lines.append("  layout is column")
        lines.append("  padding is medium")
        lines.append(f'  heading "Delete {entity}"')
        lines.append("    color is danger" if False else "    color is primary")
        lines.append('  state id is ""')
        lines.append(f'  button "Confirm delete":')
        lines.append("    on click:")
        lines.append(f'      do flow "delete_{slug}" with id: id')
        lines.append(f'      go to page "{plural}_list"')
        lines.append("")

        return "\n".join(lines).strip() + "\n"


def expand_macros(module: ast_nodes.Module, ai_callback: MacroCallback) -> ast_nodes.Module:
    return MacroExpander(ai_callback).expand_module(module)


def _sanitize_identifier(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", name).lower()
    if not cleaned or not cleaned[0].isalpha():
        cleaned = f"field_{cleaned}"
    reserved = {
        "state",
        "input",
        "button",
        "page",
        "flow",
        "macro",
        "use",
        "layout",
        "color",
        "align",
        "theme",
        "padding",
        "margin",
        "gap",
        "section",
        "when",
        "otherwise",
        "show",
        "render",
        "component",
    }
    if cleaned in reserved or cleaned in lexer.KEYWORDS:
        cleaned = f"field_{cleaned}"
    return cleaned


def _builtin_macros() -> List[ast_nodes.MacroDecl]:
    return [
        ast_nodes.MacroDecl(
            name="crud_ui",
            ai_model="codegen",
            description="Generate full CRUD UI and flows for an entity.",
            sample=None,
            parameters=["entity", "fields"],
            span=None,
        )
    ]


def default_macro_ai_callback(macro: ast_nodes.MacroDecl, args: Dict[str, Any]) -> str:
    raise MacroExpansionError(create_diagnostic("N3M-1200", message_kwargs={"name": macro.name}).message)
