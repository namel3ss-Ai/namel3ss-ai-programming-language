from __future__ import annotations

import json
import re
import os
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from . import ast_nodes
from .diagnostics.registry import create_diagnostic
from . import lexer
from .errors import Namel3ssError
from .linting import lint_module
from .parser import parse_source
from .runtime.expressions import ExpressionEvaluator, VariableEnvironment


class MacroExpansionError(Namel3ssError):
    pass


MacroCallback = Callable[[ast_nodes.MacroDecl, Dict[str, Any]], Any]

logger = logging.getLogger(__name__)


@dataclass
class RecordFieldPlan:
    name: str
    type: str = "string"
    primary_key: bool = False
    required: bool | None = None
    default: Any = None
    numeric_min: Any = None
    numeric_max: Any = None


@dataclass
class RecordPlan:
    name: str
    frame: str | None = None
    fields: list[RecordFieldPlan] = field(default_factory=list)
    description: str | None = None


@dataclass
class FlowPlan:
    name: str
    kind: str = "custom"
    record: str | None = None
    steps: list[dict[str, Any]] = field(default_factory=list)
    summary: str | None = None


@dataclass
class PagePlan:
    name: str
    route: str | None = None
    kind: str | None = None
    record: str | None = None
    layout: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class RagStagePlan:
    name: str
    stage_type: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class RagPipelinePlan:
    name: str
    stages: list[RagStagePlan] = field(default_factory=list)
    vector_store: str | None = None


@dataclass
class AgentPlan:
    name: str
    goal: str | None = None
    model: str | None = None
    tools: list[str] = field(default_factory=list)
    rag_pipeline: str | None = None


@dataclass
class MacroPlan:
    version: str | None = "1.0"
    records: list[RecordPlan] = field(default_factory=list)
    flows: list[FlowPlan] = field(default_factory=list)
    pages: list[PagePlan] = field(default_factory=list)
    rag_pipelines: list[RagPipelinePlan] = field(default_factory=list)
    agents: list[AgentPlan] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_raw(cls, raw: Any) -> "MacroPlan":
        if isinstance(raw, MacroPlan):
            return raw
        if not isinstance(raw, dict):
            raise TypeError("macro_plan must be an object")

        def _parse_record_field(field: dict[str, Any]) -> RecordFieldPlan:
            return RecordFieldPlan(
                name=str(field.get("name") or ""),
                type=str(field.get("type") or "string"),
                primary_key=bool(field.get("primary_key")),
                required=field.get("required"),
                default=field.get("default"),
                numeric_min=field.get("min"),
                numeric_max=field.get("max"),
            )

        def _parse_record(rec: dict[str, Any]) -> RecordPlan:
            fields_raw = rec.get("fields") or []
            parsed_fields = []
            for f in fields_raw:
                if isinstance(f, RecordFieldPlan):
                    parsed_fields.append(f)
                elif isinstance(f, dict):
                    parsed_fields.append(_parse_record_field(f))
            return RecordPlan(
                name=str(rec.get("name") or ""),
                frame=rec.get("frame"),
                fields=parsed_fields,
                description=rec.get("description"),
            )

        def _parse_flow(flow: dict[str, Any]) -> FlowPlan:
            return FlowPlan(
                name=str(flow.get("name") or ""),
                kind=str(flow.get("kind") or "custom"),
                record=flow.get("record"),
                steps=flow.get("steps") or [],
                summary=flow.get("summary"),
            )

        def _parse_page(page: dict[str, Any]) -> PagePlan:
            return PagePlan(
                name=str(page.get("name") or ""),
                route=page.get("route"),
                kind=page.get("kind"),
                record=page.get("record"),
                layout=page.get("layout") or [],
            )

        def _parse_stage(stage: dict[str, Any]) -> RagStagePlan:
            return RagStagePlan(
                name=str(stage.get("name") or stage.get("id") or f"stage_{len(stage)}"),
                stage_type=str(stage.get("type") or stage.get("stage_type") or ""),
                params=stage.get("params") or {k: v for k, v in stage.items() if k not in {"name", "id", "type", "stage_type"}},
            )

        def _parse_rag(pipe: dict[str, Any]) -> RagPipelinePlan:
            stages_raw = pipe.get("stages") or []
            parsed_stages = []
            for st in stages_raw:
                if isinstance(st, RagStagePlan):
                    parsed_stages.append(st)
                elif isinstance(st, dict):
                    parsed_stages.append(_parse_stage(st))
            return RagPipelinePlan(
                name=str(pipe.get("name") or pipe.get("id") or ""),
                stages=parsed_stages,
                vector_store=pipe.get("vector_store"),
            )

        def _parse_agent(agent: dict[str, Any]) -> AgentPlan:
            return AgentPlan(
                name=str(agent.get("name") or ""),
                goal=agent.get("goal"),
                model=agent.get("model"),
                tools=list(agent.get("tools") or []),
                rag_pipeline=agent.get("rag_pipeline"),
            )

        return MacroPlan(
            version=raw.get("version") or raw.get("plan_version") or "1.0",
            records=[_parse_record(r) for r in raw.get("records") or []],
            flows=[_parse_flow(f) for f in raw.get("flows") or []],
            pages=[_parse_page(p) for p in raw.get("pages") or []],
            rag_pipelines=[_parse_rag(p) for p in raw.get("rag_pipelines") or []],
            agents=[_parse_agent(a) for a in raw.get("agents") or []],
            metadata=raw.get("metadata") or {},
        )


def validate_macro_plan(plan: MacroPlan, macro_name: str | None = None) -> None:
    errors: list[str] = []

    def _err(msg: str) -> None:
        prefix = f'Macro "{macro_name}": ' if macro_name else ""
        errors.append(prefix + msg)

    record_names = set()
    for rec in plan.records:
        if not rec.name:
            _err("Record in macro_plan is missing a name.")
        elif rec.name in record_names:
            _err(f"Duplicate record '{rec.name}' in macro_plan.")
        record_names.add(rec.name)

    flow_names = set()
    for flow in plan.flows:
        if not flow.name:
            _err("Flow in macro_plan is missing a name.")
        elif flow.name in flow_names:
            _err(f"Duplicate flow '{flow.name}' in macro_plan.")
        flow_names.add(flow.name)
        if flow.record and flow.record not in record_names:
            _err(f"Flow '{flow.name}' references unknown record '{flow.record}'.")

    page_names = set()
    for page in plan.pages:
        if not page.name:
            _err("Page in macro_plan is missing a name.")
        elif page.name in page_names:
            _err(f"Duplicate page '{page.name}' in macro_plan.")
        page_names.add(page.name)
        if page.record and page.record not in record_names:
            _err(f"Page '{page.name}' references unknown record '{page.record}'.")

    rag_names = set()
    for rp in plan.rag_pipelines:
        if not rp.name:
            _err("RAG pipeline in macro_plan is missing a name.")
        elif rp.name in rag_names:
            _err(f"Duplicate RAG pipeline '{rp.name}' in macro_plan.")
        rag_names.add(rp.name)
        for st in rp.stages:
            if not st.stage_type:
                _err(f"Stage in RAG pipeline '{rp.name}' is missing a type.")

    agent_names = set()
    for ag in plan.agents:
        if not ag.name:
            _err("Agent in macro_plan is missing a name.")
        elif ag.name in agent_names:
            _err(f"Duplicate agent '{ag.name}' in macro_plan.")
        agent_names.add(ag.name)
        if ag.rag_pipeline and ag.rag_pipeline not in rag_names:
            _err(f"Agent '{ag.name}' references unknown rag_pipeline '{ag.rag_pipeline}'.")

    if errors:
        raise MacroExpansionError("; ".join(errors))

def migrate_macro_plan(plan: MacroPlan, target_version: str | None = None) -> MacroPlan:
    """
    Placeholder migration hook for structured macro plans.
    """
    if not plan.version:
        plan.version = target_version or "1.0"
    elif target_version and plan.version != target_version:
        logger.warning(
            "Macro plan version %s differs from requested %s; no migration applied.",
            plan.version,
            target_version,
        )
    return plan


def run_macro_migration(macro_name: str | None, from_version: str | None, to_version: str | None) -> str:
    source = from_version or "unknown"
    target = to_version or "latest"
    macro_label = f'macro "{macro_name}"' if macro_name else "macro plan"
    return f"{macro_label} migration from {source} to {target} is currently a no-op (versioning scaffolding is in place)."


DEFAULT_MAX_MACRO_OUTPUT_CHARS = 15000
MACRO_OUTPUT_LIMIT_ENV = "NAMEL3SS_MAX_MACRO_OUTPUT"


@dataclass
class MacroExpansionRecord:
    macro_name: str
    source_path: str | None
    span: ast_nodes.Span | None
    artifacts: dict[str, list[str]]


class MacroExpander:
    def __init__(self, ai_callback: Optional[MacroCallback], *, capture_expansions: bool = False) -> None:
        self.ai_callback = ai_callback
        self._stack: list[str] = []
        self._builtin_macros = _builtin_macros()
        self.max_output_chars = _get_max_macro_output_chars()
        self.capture_expansions = capture_expansions
        self.expansion_records: list[MacroExpansionRecord] = []
        self.current_source_path: str | None = None

    def expand_module(self, module: ast_nodes.Module, source_path: str | None = None) -> ast_nodes.Module:
        macro_registry: dict[str, ast_nodes.MacroDecl] = {m.name: m for m in self._builtin_macros}
        self.current_source_path = source_path
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

        queue: list[ast_nodes.Declaration] = list(module.declarations)
        while queue:
            decl = queue.pop(0)
            if isinstance(decl, ast_nodes.MacroUse):
                expanded = self._expand_use(decl, macro_registry)
                # Preserve declaration order: insert expanded declarations before the remaining queue.
                expanded_decls = [
                    d for d in expanded.declarations if not isinstance(d, ast_nodes.MacroDecl)
                ]
                queue = expanded_decls + queue
            elif isinstance(decl, ast_nodes.MacroTestDecl):
                # Macro tests are handled by the macro test runner, not by MacroExpander.
                continue
            elif isinstance(decl, ast_nodes.MacroDecl):
                continue
            else:
                register_decl(decl)
        self.current_source_path = None
        return ast_nodes.Module(declarations=new_decls)

    def _expand_use(self, use: ast_nodes.MacroUse, registry: Dict[str, ast_nodes.MacroDecl]) -> ast_nodes.Module:
        if use.macro_name not in registry:
            diag = create_diagnostic("N3M-1100", message_kwargs={"name": use.macro_name})
            self._raise_macro_error(use, diag)
        if use.macro_name in self._stack:
            chain = " -> ".join(self._stack + [use.macro_name])
            diag = create_diagnostic("N3M-1302", message_kwargs={"name": use.macro_name})
            detail = f"{diag.message}. Macro expansion chain: {chain}."
            self._raise_macro_error(use, detail, code=diag.code)
        macro = registry[use.macro_name]
        args = self._evaluate_args(macro, use, use.args)
        output: Any = None
        plan_result: MacroPlan | None = None
        generated_module: ast_nodes.Module | None = None
        ai_error: Exception | None = None
        if macro.name == "crud_ui":
            output = self._generate_crud_ui(args)
        elif macro.name == "app_scaffold":
            output = self._generate_app_scaffold(args)
        elif macro.name == "auth_ui":
            plan_result = self._generate_auth_ui_plan(args)
        elif macro.name == "form_ui":
            plan_result = self._generate_form_ui_plan(args)
        elif macro.name == "api_endpoints":
            plan_result = self._generate_api_endpoints_plan(args)
        elif macro.name == "analytics_dashboard":
            plan_result = self._generate_analytics_dashboard_plan(args)
        else:
            if self.ai_callback:
                try:
                    output = self.ai_callback(macro, args)
                except MacroExpansionError as exc:
                    if getattr(exc, "_macro_context_applied", False):
                        raise
                    ai_error = exc
                except Exception as exc:  # pragma: no cover - delegated to template fallback
                    ai_error = exc
            if output is None and macro.sample:
                output = self._expand_from_sample(macro, args)
            if output is None:
                if ai_error:
                    self._raise_macro_error(
                        use,
                        f"AI expansion failed for macro '{macro.name}': {ai_error}",
                        code=getattr(ai_error, "code", None),
                    )
                else:
                    self._raise_macro_error(
                        use,
                        f'Macro "{macro.name}" has no AI callback and no sample template; cannot expand.',
                    )
        self._stack.append(use.macro_name)
        try:
            if plan_result is not None:
                target_version = macro.version or plan_result.version
                plan_result = migrate_macro_plan(plan_result, target_version)
                generated_module = self._expand_structured_plan(use, plan_result)
            else:
                if output is None:
                    diag = create_diagnostic("N3M-1102", message_kwargs={"name": use.macro_name})
                    self._raise_macro_error(use, diag)
                if isinstance(output, MacroPlan):
                    target_version = macro.version or output.version
                    output = migrate_macro_plan(output, target_version)
                    generated_module = self._expand_structured_plan(use, output)
                elif isinstance(output, str):
                    output_str = output.strip()
                    if len(output_str) > self.max_output_chars:
                        diag = create_diagnostic("N3M-1300", message_kwargs={"name": use.macro_name})
                        detail = f"{diag.message} (limit {self.max_output_chars} characters, got {len(output_str)})."
                        self._raise_macro_error(use, detail, code=diag.code, generated=output)
                    parsed_plan = None
                    try:
                        parsed_json = json.loads(output_str)
                        if isinstance(parsed_json, dict) and "macro_plan" in parsed_json:
                            parsed_plan = MacroPlan.from_raw(parsed_json.get("macro_plan"))
                    except Exception:
                        parsed_plan = None
                    if parsed_plan is not None:
                        parsed_plan = migrate_macro_plan(parsed_plan, macro.version or parsed_plan.version)
                        generated_module = self._expand_structured_plan(use, parsed_plan)
                    else:
                        if "```" in output_str or "`" in output_str:
                            diag = create_diagnostic("N3M-1301", message_kwargs={"name": use.macro_name})
                            detail = f"{diag.message} Backticks are not allowed in macro output."
                            self._raise_macro_error(use, detail, code=diag.code, generated=output)
                        generated_module = self._parse_generated(use, output_str)
                elif isinstance(output, ast_nodes.Module):
                    generated_module = output
                else:
                    diag = create_diagnostic("N3M-1102", message_kwargs={"name": use.macro_name})
                    self._raise_macro_error(use, diag)

            if generated_module and any(
                isinstance(d, ast_nodes.MacroUse) and d.macro_name == use.macro_name
                for d in generated_module.declarations
            ):
                diag = create_diagnostic("N3M-1302", message_kwargs={"name": use.macro_name})
                self._raise_macro_error(use, diag, generated=output)
            generated_module = self._expand_nested_module(
                ast_nodes.Module(
                    declarations=[d for d in generated_module.declarations if not isinstance(d, ast_nodes.MacroDecl)]
                ),
                registry,
            )
            findings = lint_module(generated_module)
            if findings:
                diag = create_diagnostic("N3M-1202", message_kwargs={"name": use.macro_name})
                self._raise_macro_error(use, diag, generated=output)
            if not generated_module.declarations:
                diag = create_diagnostic("N3M-1103", message_kwargs={"name": use.macro_name})
                self._raise_macro_error(use, diag, generated=output)
            if self.capture_expansions and generated_module:
                self._record_macro_artifacts(use, generated_module)
            return generated_module
        except MacroExpansionError as exc:
            if getattr(exc, "_macro_context_applied", False):
                raise
            raise self._raise_macro_error(use, str(exc), attach=False, generated=output)
        except Exception as exc:  # pragma: no cover - safety net
            raise self._raise_macro_error(use, str(exc), generated=output)
        finally:
            self._stack.pop()

    def _parse_generated(self, use: ast_nodes.MacroUse, source: str) -> ast_nodes.Module:
        try:
            return parse_source(source)
        except Exception as exc:
            diag = create_diagnostic("N3M-1201", message_kwargs={"detail": str(exc)})
            self._raise_macro_error(use, diag, generated=source)

    def _expand_nested_module(self, module: ast_nodes.Module, registry: Dict[str, ast_nodes.MacroDecl]) -> ast_nodes.Module:
        """
        Recursively expand MacroUse declarations within a module, preserving declaration order.
        """
        expanded_decls: list[ast_nodes.Declaration] = []
        for decl in module.declarations:
            if isinstance(decl, ast_nodes.MacroUse):
                nested = self._expand_use(decl, registry)
                nested_expanded = self._expand_nested_module(
                    ast_nodes.Module(declarations=[d for d in nested.declarations if not isinstance(d, ast_nodes.MacroDecl)]),
                    registry,
                )
                expanded_decls.extend(nested_expanded.declarations)
            elif isinstance(decl, ast_nodes.MacroDecl):
                continue
            else:
                expanded_decls.append(decl)
        return ast_nodes.Module(declarations=expanded_decls)

    def _record_macro_artifacts(self, use: ast_nodes.MacroUse, module: ast_nodes.Module) -> None:
        artifacts: dict[str, list[str]] = {
            "records": [],
            "flows": [],
            "pages": [],
            "rag_pipelines": [],
            "agents": [],
        }
        for decl in module.declarations:
            if isinstance(decl, ast_nodes.RecordDecl):
                artifacts["records"].append(decl.name)
            elif isinstance(decl, ast_nodes.FlowDecl):
                artifacts["flows"].append(decl.name)
            elif isinstance(decl, ast_nodes.PageDecl):
                artifacts["pages"].append(decl.name)
            elif isinstance(decl, ast_nodes.RagPipelineDecl):
                artifacts["rag_pipelines"].append(decl.name)
            elif isinstance(decl, ast_nodes.AgentDecl):
                artifacts["agents"].append(decl.name)
        self.expansion_records.append(
            MacroExpansionRecord(
                macro_name=use.macro_name,
                source_path=self.current_source_path,
                span=use.span,
                artifacts=artifacts,
            )
        )

    def _evaluate_args(self, macro: ast_nodes.MacroDecl, use: ast_nodes.MacroUse, args: Dict[str, ast_nodes.Expr | Any]) -> Dict[str, Any]:
        env = VariableEnvironment()
        evaluator = ExpressionEvaluator(env, resolver=lambda name: (False, None))
        evaluated: dict[str, Any] = {}
        if macro.parameters:
            for param in macro.parameters:
                if param not in args:
                    diag = create_diagnostic("N3M-1101", message_kwargs={"name": param})
                    self._raise_macro_error(use, diag)
        current_key: str | None = None
        try:
            for key, expr in args.items():
                current_key = key
                if key == "fields" and isinstance(expr, list) and all(isinstance(f, ast_nodes.MacroFieldSpec) for f in expr):
                    evaluated[key] = expr
                    continue
                if isinstance(expr, ast_nodes.Expr):
                    evaluated[key] = evaluator.evaluate(expr)
                else:
                    evaluated[key] = expr
            return evaluated
        except Exception:
            friendly = (
                f"Invalid macro argument '{current_key}'. Macro parameters currently support only literal values "
                "(strings, numbers, booleans, lists). Referencing variables or calling functions is not supported."
            )
            self._raise_macro_error(use, friendly, code="N3M-1101")

    def _raise_macro_error(
        self,
        use: ast_nodes.MacroUse,
        message_or_diag: str | Any,
        *,
        code: Optional[str] = None,
        generated: Optional[str] = None,
        attach: bool = True,
    ) -> MacroExpansionError:
        message = message_or_diag.message if hasattr(message_or_diag, "message") else str(message_or_diag)
        diag_code = code or getattr(message_or_diag, "code", None)
        location = ""
        if use.span:
            location = f" at line {use.span.line}, column {use.span.column}"
        snippet = ""
        if generated:
            lines = [ln.rstrip() for ln in generated.strip().splitlines()[:3] if ln.strip() != ""]
            if lines:
                snippet = "\nGenerated snippet:\n" + "\n".join(lines)
        code_suffix = f" ({diag_code})" if diag_code else ""
        final_message = f'Macro "{use.macro_name}"{location}{code_suffix}: {message}{snippet}'
        err = MacroExpansionError(final_message)
        err._macro_context_applied = True  # type: ignore[attr-defined]
        if attach:
            raise err
        return err

    def _normalize_entity_fields(
        self, args: Dict[str, Any]
    ) -> tuple[str, str, str, str, str, list[ast_nodes.MacroFieldSpec]]:
        entity = args.get("entity")
        fields = args.get("fields")
        if not isinstance(entity, str) or not entity.strip():
            raise MacroExpansionError(create_diagnostic("N3M-5000").message)
        entity = entity.strip()
        raw_field_specs: list[ast_nodes.MacroFieldSpec] = []
        if isinstance(fields, list) and fields and all(isinstance(f, ast_nodes.MacroFieldSpec) for f in fields):
            raw_field_specs = fields  # type: ignore[assignment]
        elif isinstance(fields, list) and all(isinstance(f, str) and f.strip() for f in fields):
            raw_field_specs = [
                ast_nodes.MacroFieldSpec(
                    name=f.strip(),
                    field_type=None,
                    required=None,
                    min_expr=None,
                    max_expr=None,
                    default_expr=None,
                )
                for f in fields
            ]
        else:
            raise MacroExpansionError(create_diagnostic("N3M-5001").message)

        if not raw_field_specs:
            raise MacroExpansionError(create_diagnostic("N3M-5001").message)

        slug = _sanitize_identifier(entity)
        plural = slug if slug.endswith("s") else f"{slug}s"
        frame_name = f"{plural}_frame"
        id_field = f"{slug}_id"

        field_specs: list[ast_nodes.MacroFieldSpec] = []
        for spec in raw_field_specs:
            field_specs.append(
                ast_nodes.MacroFieldSpec(
                    name=spec.name,
                    field_type=spec.field_type or "string",
                    required=True if spec.required is True else False,
                    min_expr=spec.min_expr,
                    max_expr=spec.max_expr,
                    default_expr=spec.default_expr,
                    span=spec.span,
                )
            )
        return entity, slug, plural, frame_name, id_field, field_specs

    def _render_crud_scaffold(
        self,
        entity: str,
        slug: str,
        plural: str,
        frame_name: str,
        id_field: str,
        field_specs: list[ast_nodes.MacroFieldSpec],
    ) -> list[str]:
        def _label(name: str) -> str:
            return name.strip().replace("_", " ").title()

        def _state_default(spec: ast_nodes.MacroFieldSpec) -> str:
            if spec.default_expr is not None:
                return _render_expr(spec.default_expr)
            ftype = (spec.field_type or "").lower()
            if ftype in {"int", "integer", "float", "number", "decimal"}:
                return "0"
            if ftype in {"bool", "boolean"}:
                return "false"
            return "\"\""

        lines: list[str] = []
        bool_filter = next((s for s in field_specs if (s.field_type or "").lower() in {"bool", "boolean"}), None)
        order_field = _sanitize_identifier(
            next((s.name for s in field_specs if (s.field_type or "").lower() in {"string", "text"}), id_field)
        )

        # Frame declaration
        lines.append(f'frame is "{frame_name}":')
        lines.append("  source:")
        lines.append('    backend is "memory"')
        lines.append(f'    table is "{plural}"')
        lines.append("")

        # Record declaration
        lines.append(f'record is "{entity}":')
        lines.append(f'  frame is "{frame_name}"')
        lines.append("  fields:")
        lines.append(f"    {id_field}:")
        lines.append('      type is "uuid"')
        lines.append("      primary_key is true")
        lines.append("      required is true")
        for spec in field_specs:
            field_id = _sanitize_identifier(spec.name)
            lines.append(f"    {field_id}:")
            lines.append(f'      type is "{spec.field_type or "string"}"')
            lines.append(f"      required is {'true' if spec.required else 'false'}")
            if spec.default_expr is not None:
                lines.append(f"      default is {_render_expr(spec.default_expr)}")
            if spec.min_expr is not None:
                lines.append(f"      must be at least {_render_expr(spec.min_expr)}")
            if spec.max_expr is not None:
                lines.append(f"      must be at most {_render_expr(spec.max_expr)}")
        lines.append("")

        # Flows
        list_flow = f"list_{plural}"
        create_flow = f"create_{slug}"
        edit_flow = f"edit_{slug}"
        delete_flow = f"delete_{slug}"
        get_flow = f"get_{slug}"

        lines.append(f'flow is "{list_flow}":')
        lines.append('  step is "load":')
        lines.append(f"    find {plural} where:")
        if bool_filter:
            lines.append(f"      {_sanitize_identifier(bool_filter.name)} is true")
        else:
            lines.append(f"      {id_field} is not null")
        lines.append(f"    order {plural} by {order_field} ascending")
        lines.append("")

        lines.append(f'flow is "{create_flow}":')
        lines.append('  step is "create":')
        lines.append('    kind is "db_create"')
        lines.append(f'    record is "{entity}"')
        lines.append("    values:")
        lines.append(f"      {id_field}: random_uuid()")
        for spec in field_specs:
            field_id = _sanitize_identifier(spec.name)
            lines.append(f"      {field_id}: state.{field_id}")
        lines.append("")

        lines.append(f'flow is "{edit_flow}":')
        lines.append('  step is "update":')
        lines.append('    kind is "db_update"')
        lines.append(f'    record is "{entity}"')
        lines.append("    by id:")
        lines.append(f"      {id_field}: state.{id_field}")
        lines.append("    set:")
        for spec in field_specs:
            field_id = _sanitize_identifier(spec.name)
            lines.append(f"      {field_id}: state.{field_id}")
        lines.append("")

        lines.append(f'flow is "{delete_flow}":')
        lines.append('  step is "delete":')
        lines.append('    kind is "db_delete"')
        lines.append(f'    record is "{entity}"')
        lines.append("    by id:")
        lines.append(f"      {id_field}: state.{id_field}")
        lines.append("")

        lines.append(f'flow is "{get_flow}":')
        lines.append('  step is "fetch":')
        lines.append(f"    find {plural} where:")
        lines.append(f"      {id_field} is state.{id_field}")
        lines.append("")

        # Pages
        lines.append(f'page is "{plural}_list" at "/{plural}":')
        lines.append('  section is "content":')
        lines.append(f'    heading "{entity} List"')
        lines.append(f'    button "Create {entity}":')
        lines.append("      on click:")
        lines.append(f'        go to page "{slug}_create"')
        lines.append(f'    button "Refresh {entity}s":')
        lines.append("      on click:")
        lines.append(f'        do flow "{list_flow}"')
        lines.append("")

        lines.append(f'page is "{slug}_create" at "/{plural}/new":')
        lines.append('  section is "content":')
        lines.append(f'    heading "Create {entity}"')
        for spec in field_specs:
            field_id = _sanitize_identifier(spec.name)
            lines.append(f"    state {field_id} is {_state_default(spec)}")
        for spec in field_specs:
            field_id = _sanitize_identifier(spec.name)
            lines.append(f'    input "{_label(spec.name)}" as {field_id}')
        lines.append(f'    button "Save {entity}":')
        lines.append("      on click:")
        save_pairs = ", ".join(f"{_sanitize_identifier(spec.name)}: {_sanitize_identifier(spec.name)}" for spec in field_specs)
        lines.append(f'        do flow "{create_flow}" with {save_pairs}')
        lines.append(f'        go to page "{plural}_list"')
        lines.append("")

        lines.append(f'page is "{slug}_edit" at "/{plural}/edit":')
        lines.append('  section is "content":')
        lines.append(f'    heading "Edit {entity}"')
        lines.append(f"    state {id_field} is \"\"")
        for spec in field_specs:
            field_id = _sanitize_identifier(spec.name)
            lines.append(f"    state {field_id} is {_state_default(spec)}")
        lines.append(f'    input "{_label("id")}" as {id_field}')
        for spec in field_specs:
            field_id = _sanitize_identifier(spec.name)
            lines.append(f'    input "{_label(spec.name)}" as {field_id}')
        lines.append(f'    button "Update {entity}":')
        lines.append("      on click:")
        update_pairs = ", ".join(
            [f"{_sanitize_identifier(spec.name)}: {_sanitize_identifier(spec.name)}" for spec in field_specs] + [f"{id_field}: {id_field}"]
        )
        lines.append(f'        do flow "{edit_flow}" with {update_pairs}')
        lines.append(f'        go to page "{plural}_list"')
        lines.append(f'    button "Delete {entity}":')
        lines.append("      on click:")
        lines.append(f'        do flow "{delete_flow}" with {id_field}: {id_field}')
        lines.append(f'        go to page "{plural}_list"')
        lines.append("")

        lines.append(f'page is "{slug}_delete" at "/{plural}/delete":')
        lines.append('  section is "content":')
        lines.append(f'    heading "Delete {entity}"')
        lines.append(f"    state {id_field} is \"\"")
        lines.append(f'    input "{_label("id")}" as {id_field}')
        lines.append(f'    button "Confirm delete":')
        lines.append("      on click:")
        lines.append(f'        do flow "{delete_flow}" with {id_field}: {id_field}')
        lines.append(f'        go to page "{plural}_list"')
        lines.append("")

        lines.append(f'page is "{slug}_detail" at "/{plural}/detail":')
        lines.append('  section is "content":')
        lines.append(f'    heading "{entity} Detail"')
        lines.append(f"    state {id_field} is \"\"")
        lines.append(f'    button "Load {entity}":')
        lines.append("      on click:")
        lines.append(f'        do flow "{get_flow}" with {id_field}: {id_field}')
        lines.append(f'    button "Back to list":')
        lines.append("      on click:")
        lines.append(f'        go to page "{plural}_list"')
        lines.append("")

        return lines

    def _expand_structured_plan(self, use: ast_nodes.MacroUse, plan_raw: Any) -> ast_nodes.Module:
        try:
            plan = MacroPlan.from_raw(plan_raw)
        except Exception as exc:
            self._raise_macro_error(use, f"Structured macro_plan must be an object. {exc}", code="N3M-1400")

        validate_macro_plan(plan, use.macro_name)

        lines: list[str] = []

        def _field_line(key: str, val: Any, indent: int = 0, dest: Optional[list[str]] = None) -> None:
            pad = "  " * indent
            if isinstance(val, bool):
                sval = "true" if val else "false"
            elif val is None:
                sval = "null"
            elif isinstance(val, (int, float)):
                sval = str(val)
            else:
                sval = f"\"{val}\""
            if key.startswith("must be "):
                rendered = f"{pad}{key} {sval}"
            else:
                rendered = f"{pad}{key} is {sval}"
            (dest or lines).append(rendered)

        record_fields: dict[str, dict[str, Any]] = {}

        # Records
        for rec in plan.records:
            frame = rec.frame or f"{rec.name.lower()}s"
            record_fields[rec.name] = {"fields": [], "primary_key": None}
            record_lines: list[str] = []
            record_lines.append(f'record is "{rec.name}":')
            record_lines.append(f'  frame is "{frame}"')
            record_lines.append("  fields:")
            for field in rec.fields:
                fid = _sanitize_identifier(field.name)
                is_pk = bool(field.primary_key)
                record_lines.append(f"    {fid}:")
                ftype = field.type or "string"
                record_lines.append(f'      type is "{ftype}"')
                if is_pk:
                    record_lines.append("      primary_key is true")
                if field.required is not None:
                    record_lines.append(f'      required is {"true" if field.required else "false"}')
                if field.default is not None:
                    _field_line("default", field.default, indent=3, dest=record_lines)
                if field.numeric_min is not None:
                    _field_line("must be at least", field.numeric_min, indent=3, dest=record_lines)
                if field.numeric_max is not None:
                    _field_line("must be at most", field.numeric_max, indent=3, dest=record_lines)
                record_fields[rec.name]["fields"].append({"id": fid, "is_pk": is_pk})
                if is_pk:
                    record_fields[rec.name]["primary_key"] = fid
            # If no primary key provided, add a default id
            if record_fields[rec.name]["primary_key"] is None:
                default_pk = f"{_sanitize_identifier(rec.name)}_id"
                record_lines.append(f"    {default_pk}:")
                record_lines.append('      type is "uuid"')
                record_lines.append("      primary_key is true")
                record_lines.append("      required is true")
                record_fields[rec.name]["fields"].insert(0, {"id": default_pk, "is_pk": True})
                record_fields[rec.name]["primary_key"] = default_pk
            lines.extend(record_lines)
            lines.append("")

        # Flows (CRUD-kind-aware)
        for flow in plan.flows:
            fname = flow.name
            kind = (flow.kind or "").strip().lower()
            record = flow.record
            if kind in {"list_crud", "create_crud", "edit_crud", "delete_crud", "api_list", "api_get", "api_create", "api_update", "api_delete"}:
                if not record:
                    self._raise_macro_error(use, f"Flow '{fname}' requires a record name.", code="N3M-1402")
                rec_spec = record_fields.get(record, {"fields": [], "primary_key": None})
                pk_field = rec_spec.get("primary_key") or "id"
                non_pk_fields = [f["id"] for f in rec_spec.get("fields", []) if not f.get("is_pk")]
                plural = record.lower() if record.lower().endswith("s") else f"{record.lower()}s"
                # Leverage existing CRUD patterns via DSL snippets.
                if kind in {"list_crud", "api_list"}:
                    lines.append(f'flow is "{fname}":')
                    lines.append('  step is "load":')
                    lines.append(f"    find {plural} where:")
                    lines.append(f"      {pk_field} is not null")
                    order_field = non_pk_fields[0] if non_pk_fields else pk_field
                    lines.append(f"    order {plural} by {order_field} ascending")
                    lines.append("")
                elif kind in {"create_crud", "api_create"}:
                    lines.append(f'flow is "{fname}":')
                    lines.append('  step is "create":')
                    lines.append('    kind is "db_create"')
                    lines.append(f'    record is "{record}"')
                    lines.append("    values:")
                    lines.append(f"      {pk_field}: random_uuid()")
                    for field_id in non_pk_fields:
                        lines.append(f"      {field_id}: state.{field_id}")
                    lines.append("")
                elif kind in {"edit_crud", "api_update"}:
                    lines.append(f'flow is "{fname}":')
                    lines.append('  step is "update":')
                    lines.append('    kind is "db_update"')
                    lines.append(f'    record is "{record}"')
                    lines.append("    by id:")
                    lines.append(f"      {pk_field}: state.{pk_field}")
                    lines.append("    set:")
                    if non_pk_fields:
                        for field_id in non_pk_fields:
                            lines.append(f"      {field_id}: state.{field_id}")
                    else:
                        lines.append(f"      {pk_field}: state.{pk_field}")
                    lines.append("")
                elif kind in {"delete_crud", "api_delete"}:
                    lines.append(f'flow is "{fname}":')
                    lines.append('  step is "delete":')
                    lines.append('    kind is "db_delete"')
                    lines.append(f'    record is "{record}"')
                    lines.append("    by id:")
                    lines.append(f"      {pk_field}: state.{pk_field}")
                    lines.append("")
                elif kind == "api_get":
                    lines.append(f'flow is "{fname}":')
                    lines.append('  step is "load":')
                    lines.append(f"    find {plural} where:")
                    lines.append(f"      {pk_field} is state.{pk_field}")
                    lines.append(f"    limit {plural} to 1")
                    lines.append("")
            else:
                lines.append(f'flow is "{fname}":')
                if flow.summary:
                    lines.append(f'  description is "{flow.summary}"')
                if flow.steps:
                    for idx, step in enumerate(flow.steps):
                        sname = step.get("name") if isinstance(step, dict) else f"step_{idx}"
                        skind = step.get("kind") if isinstance(step, dict) else "log"
                        starget = step.get("target") if isinstance(step, dict) else None
                        message = step.get("message") if isinstance(step, dict) else None
                        lines.append(f'  step is "{sname or f"step_{idx}"}":')
                        lines.append(f'    kind is "{skind or "log"}"')
                        if starget is None and (skind or "").lower() == "log":
                            starget = "info"
                        if starget:
                            lines.append(f'    target is "{starget}"')
                        if message:
                            lines.append(f'    message is "{message}"')
                else:
                    lines.append('  step is "log":')
                    lines.append('    kind is "log"')
                    lines.append('    target is "info"')
                    lines.append(f'    message is "Flow {fname} ran."')
                lines.append("")

        # Pages (very lightweight scaffolding)
        for page in plan.pages:
            route = page.route or "/"
            pkind = (page.kind or "").strip().lower()
            record = page.record
            record_slug = _sanitize_identifier(record) if record else None
            plural = record_slug if record_slug and record_slug.endswith("s") else f"{record_slug}s" if record_slug else None
            lines.append(f'page is "{page.name}" at "{route}":')
            lines.append('  section is "content":')
            if pkind == "crud_list" and record:
                lines.append(f'    heading "{record} List"')
                lines.append(f'    button "Refresh {record}s":')
                lines.append("      on click:")
                lines.append(f'        do flow "list_{plural}"')
            elif pkind in {"crud_form", "form"} and record:
                lines.append(f'    heading "{record} Form"')
                lines.append(f'    button "Save {record}":')
                lines.append("      on click:")
                lines.append(f'        do flow "create_{record_slug}"')
            elif pkind == "dashboard":
                lines.append(f'    heading "{page.name} Dashboard"')
            else:
                lines.append(f'    heading "{page.name}"')
            lines.append("")

        # RAG pipelines
        for pipeline in plan.rag_pipelines:
            lines.append(f'rag pipeline is "{pipeline.name}":')
            if pipeline.vector_store:
                lines.append(f'  using vector_store is "{pipeline.vector_store}"')
            for stage in pipeline.stages:
                lines.append(f'  stage is "{stage.name}":')
                lines.append(f'    type is "{stage.stage_type}"')
                for pk, pv in (stage.params or {}).items():
                    if isinstance(pv, (dict, list)):
                        rendered = json.dumps(pv)
                        lines.append(f'    {pk} is "{rendered}"')
                    elif isinstance(pv, str):
                        lines.append(f'    {pk} is "{pv}"')
                    else:
                        lines.append(f"    {pk} is {pv}")
            lines.append("")

        # Agents
        for agent in plan.agents:
            model_name = agent.model or "gpt-4.1-mini"
            lines.append(f'ai is "{agent.name}":')
            lines.append(f'  model is "{model_name}"')
            if agent.tools:
                lines.append("  tools:")
                for tool in agent.tools:
                    lines.append(f'    - "{tool}"')
            lines.append("")
            lines.append(f'agent is "{agent.name}":')
            if agent.goal:
                lines.append(f'  goal is "{agent.goal}"')
            else:
                lines.append('  goal is "Handle tasks generated from macro plan."')
            lines.append("")

        rendered = "\n".join(lines).strip() + ("\n" if lines else "")
        if not rendered.strip():
            self._raise_macro_error(use, "Structured macro_plan produced no declarations.", code="N3M-1103")
        return self._parse_generated(use, rendered)

    def _expand_from_sample(self, macro: ast_nodes.MacroDecl, args: Dict[str, Any]) -> str | None:
        template = macro.sample
        if not template:
            return None

        def _stringify(val: Any) -> str:
            if isinstance(val, (dict, list)):
                try:
                    return json.dumps(val)
                except Exception:
                    return str(val)
            return str(val)

        def repl(match: re.Match[str]) -> str:
            key = match.group(1)
            if key in args:
                return _stringify(args[key])
            return match.group(0)

        substituted = re.sub(r"{([A-Za-z_][A-Za-z0-9_]*)}", repl, template)
        # Allow simple escaped newlines/backslashes inside templates
        substituted = substituted.replace("\\n", "\n").replace("\\\\", "\\")
        return substituted


    def _convert_macro_fields(self, fields: list[Any]) -> list[RecordFieldPlan]:
        record_fields: list[RecordFieldPlan] = []
        for spec in fields or []:
            if isinstance(spec, RecordFieldPlan):
                record_fields.append(spec)
            elif isinstance(spec, ast_nodes.MacroFieldSpec):
                default_val = None
                if isinstance(spec.default_expr, ast_nodes.Literal):
                    default_val = spec.default_expr.value
                elif spec.default_expr is not None:
                    default_val = _render_expr(spec.default_expr)
                min_val = None
                if isinstance(spec.min_expr, ast_nodes.Literal):
                    min_val = spec.min_expr.value
                elif spec.min_expr is not None:
                    min_val = _render_expr(spec.min_expr)
                max_val = None
                if isinstance(spec.max_expr, ast_nodes.Literal):
                    max_val = spec.max_expr.value
                elif spec.max_expr is not None:
                    max_val = _render_expr(spec.max_expr)
                record_fields.append(
                    RecordFieldPlan(
                        name=spec.name,
                        type=spec.field_type or "string",
                        required=spec.required,
                        numeric_min=min_val,
                        numeric_max=max_val,
                        default=default_val,
                    )
                )
            elif isinstance(spec, dict):
                record_fields.append(
                    RecordFieldPlan(
                        name=str(spec.get("name") or ""),
                        type=str(spec.get("type") or spec.get("field_type") or "string"),
                        required=spec.get("required"),
                        numeric_min=spec.get("min"),
                        numeric_max=spec.get("max"),
                        default=spec.get("default"),
                        primary_key=bool(spec.get("primary_key")),
                    )
                )
        return record_fields

    def _generate_crud_ui(self, args: Dict[str, Any]) -> str:
        entity, slug, plural, frame_name, id_field, field_specs = self._normalize_entity_fields(args)
        lines = self._render_crud_scaffold(entity, slug, plural, frame_name, id_field, field_specs)
        return "\n".join(lines).strip() + "\n"

    def _generate_app_scaffold(self, args: Dict[str, Any]) -> str:
        entity, slug, plural, frame_name, id_field, field_specs = self._normalize_entity_fields(args)
        crud_lines = self._render_crud_scaffold(entity, slug, plural, frame_name, id_field, field_specs)

        docs_frame = f"{slug}_docs"
        vector_store = f"{slug}_kb"
        pipeline = f"{slug}_kb_pipeline"
        ai_name = f"{slug}_support_ai"
        agent_name = f"{slug}_support_agent"
        eval_frame = f"{slug}_eval_questions"
        eval_name = f"{slug}_support_eval"
        text_field = next(
            (_sanitize_identifier(f.name) for f in field_specs if (f.field_type or "").lower() in {"string", "text"}),
            "content",
        )

        rag_lines: list[str] = []
        rag_lines.append(f'frame is "{docs_frame}":')
        rag_lines.append("  source:")
        rag_lines.append('    backend is "memory"')
        rag_lines.append(f'    table is "{docs_frame}"')
        rag_lines.append("  select:")
        rag_lines.append(f'    columns are ["{id_field}", "{text_field}"]')
        rag_lines.append("")

        rag_lines.append(f'vector_store is "{vector_store}":')
        rag_lines.append('  backend is "memory"')
        rag_lines.append(f'  frame is "{docs_frame}"')
        rag_lines.append(f'  text_column is "{text_field}"')
        rag_lines.append(f'  id_column is "{id_field}"')
        rag_lines.append('  embedding_model is "default_embedding"')
        rag_lines.append("")

        rag_lines.append(f'ai is "{ai_name}":')
        rag_lines.append('  model is "gpt-4.1-mini"')
        rag_lines.append('  provider is "openai_default"')
        rag_lines.append("")

        rag_lines.append(f'rag pipeline is "{pipeline}":')
        rag_lines.append('  stage is "retrieve":')
        rag_lines.append('    type is "vector_retrieve"')
        rag_lines.append(f'    vector_store is "{vector_store}"')
        rag_lines.append("    top_k is 5")
        rag_lines.append('  stage is "answer":')
        rag_lines.append('    type is "ai_answer"')
        rag_lines.append(f'    ai is "{ai_name}"')
        rag_lines.append("")

        rag_lines.append(f'agent is "{agent_name}":')
        rag_lines.append(f'  goal is "Help users with questions about {entity}."')
        rag_lines.append(f'  personality is "You are a helpful support agent for {entity}."')
        rag_lines.append("")

        rag_lines.append(f'frame is "{eval_frame}":')
        rag_lines.append("  source:")
        rag_lines.append('    backend is "memory"')
        rag_lines.append(f'    table is "{eval_frame}"')
        rag_lines.append("  select:")
        rag_lines.append('    columns are ["question", "expected_answer"]')
        rag_lines.append("")

        rag_lines.append(f'rag evaluation is "{eval_name}":')
        rag_lines.append(f'  pipeline is "{pipeline}"')
        rag_lines.append("  dataset:")
        rag_lines.append(f'    from frame "{eval_frame}"')
        rag_lines.append('    question_column is "question"')
        rag_lines.append('    answer_column is "expected_answer"')
        rag_lines.append("")

        combined = "\n".join(crud_lines + rag_lines).strip() + "\n"
        return combined

    def _generate_auth_ui_plan(self, args: Dict[str, Any]) -> MacroPlan:
        record_name = args.get("record") or args.get("entity") or "User"
        slug = _sanitize_identifier(record_name)
        plural = slug if slug.endswith("s") else f"{slug}s"
        fields = self._convert_macro_fields(
            args.get("fields")
            or [
                ast_nodes.MacroFieldSpec(name="email", field_type="string", required=True),
                ast_nodes.MacroFieldSpec(name="password", field_type="string", required=True),
            ]
        )
        record = RecordPlan(name=record_name, frame=f"{plural}_auth", fields=fields)
        flows = [
            FlowPlan(name=f"create_{slug}", kind="create_crud", record=record_name),
            FlowPlan(name=f"list_{plural}", kind="list_crud", record=record_name),
            FlowPlan(
                name=f"authenticate_{slug}",
                kind="custom",
                record=record_name,
                steps=[{"name": "verify_credentials", "kind": "log", "message": "Authenticate user credentials."}],
            ),
        ]
        pages = [
            PagePlan(name=f"{slug}_login", route="/login", kind="crud_form", record=record_name),
            PagePlan(name=f"{slug}_home", route="/home", kind="dashboard", record=record_name),
        ]
        return MacroPlan(records=[record], flows=flows, pages=pages)

    def _generate_form_ui_plan(self, args: Dict[str, Any]) -> MacroPlan:
        record_name = args.get("record") or args.get("entity") or "FormData"
        slug = _sanitize_identifier(record_name)
        plural = slug if slug.endswith("s") else f"{slug}s"
        fields = self._convert_macro_fields(args.get("fields") or [])
        record = RecordPlan(name=record_name, frame=f"{plural}_data", fields=fields)
        flows = [FlowPlan(name=f"create_{slug}", kind="create_crud", record=record_name)]
        pages = [PagePlan(name=f"{slug}_form", route=f"/{slug}/form", kind="form", record=record_name)]
        return MacroPlan(records=[record], flows=flows, pages=pages)

    def _generate_api_endpoints_plan(self, args: Dict[str, Any]) -> MacroPlan:
        record_name = args.get("record") or args.get("entity") or "Resource"
        slug = _sanitize_identifier(record_name)
        plural = slug if slug.endswith("s") else f"{slug}s"
        fields = self._convert_macro_fields(args.get("fields") or [])
        record = RecordPlan(name=record_name, frame=f"{plural}_api", fields=fields)
        flows = [
            FlowPlan(name=f"list_{plural}", kind="api_list", record=record_name),
            FlowPlan(name=f"get_{slug}", kind="api_get", record=record_name),
            FlowPlan(name=f"create_{slug}", kind="api_create", record=record_name),
            FlowPlan(name=f"update_{slug}", kind="api_update", record=record_name),
            FlowPlan(name=f"delete_{slug}", kind="api_delete", record=record_name),
        ]
        return MacroPlan(records=[record], flows=flows)

    def _generate_analytics_dashboard_plan(self, args: Dict[str, Any]) -> MacroPlan:
        record_name = args.get("record") or args.get("entity") or "Metric"
        slug = _sanitize_identifier(record_name)
        plural = slug if slug.endswith("s") else f"{slug}s"
        fields = self._convert_macro_fields(
            args.get("fields")
            or [
                RecordFieldPlan(name="metric_name", type="string", required=True),
                RecordFieldPlan(name="metric_value", type="number", required=True),
            ]
        )
        record = RecordPlan(name=record_name, frame=f"{plural}_analytics", fields=fields)
        flows = [
            FlowPlan(name=f"list_{plural}", kind="list_crud", record=record_name),
            FlowPlan(
                name=f"summarise_{plural}",
                kind="custom",
                record=record_name,
                steps=[{"name": "summarise", "kind": "log", "message": "Summarise recent metrics."}],
            ),
        ]
        rag_pipeline = RagPipelinePlan(
            name=f"{slug}_insights",
            stages=[
                RagStagePlan(name="vector", stage_type="vector_retrieve", params={"top_k": 3}),
                RagStagePlan(name="answer", stage_type="ai_answer", params={"ai": f"{slug}_analyst"}),
            ],
        )
        agent = AgentPlan(
            name=f"{slug}_analyst",
            goal="Summarise analytics and answer questions.",
            model=args.get("model") or "gpt-4.1-mini",
            tools=list(args.get("tools") or []),
            rag_pipeline=rag_pipeline.name,
        )
        pages = [PagePlan(name=f"{slug}_dashboard", route="/dashboard", kind="dashboard", record=record_name)]
        return MacroPlan(records=[record], flows=flows, pages=pages, rag_pipelines=[rag_pipeline], agents=[agent])


def expand_macros(module: ast_nodes.Module, ai_callback: MacroCallback) -> ast_nodes.Module:
    return MacroExpander(ai_callback).expand_module(module)


def _get_max_macro_output_chars() -> int:
    override = os.environ.get(MACRO_OUTPUT_LIMIT_ENV)
    if override:
        try:
            value = int(override)
            if value > 0:
                return value
        except Exception:
            pass
    return DEFAULT_MAX_MACRO_OUTPUT_CHARS


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
            version="1.0",
            span=None,
        ),
        ast_nodes.MacroDecl(
            name="app_scaffold",
            ai_model="codegen",
            description="Generate a full app scaffold (CRUD + RAG + agent) for an entity.",
            sample=None,
            parameters=["entity", "fields"],
            version="1.0",
            span=None,
        ),
        ast_nodes.MacroDecl(
            name="auth_ui",
            ai_model="codegen",
            description="Generate login/logout flows and pages for a user record.",
            sample=None,
            parameters=[],
            version="1.0",
            span=None,
        ),
        ast_nodes.MacroDecl(
            name="form_ui",
            ai_model="codegen",
            description="Generate a simple form page and supporting flow for a record.",
            sample=None,
            parameters=[],
            version="1.0",
            span=None,
        ),
        ast_nodes.MacroDecl(
            name="api_endpoints",
            ai_model="codegen",
            description="Generate list/get/create/update/delete flows as API endpoints.",
            sample=None,
            parameters=[],
            version="1.0",
            span=None,
        ),
        ast_nodes.MacroDecl(
            name="analytics_dashboard",
            ai_model="codegen",
            description="Generate a simple analytics dashboard page plus supporting flows.",
            sample=None,
            parameters=[],
            version="1.0",
            span=None,
        ),
    ]


def _render_expr(expr: ast_nodes.Expr | None) -> str:
    if expr is None:
        return ""
    if isinstance(expr, ast_nodes.Literal):
        val = expr.value
        if isinstance(val, str):
            return f"\"{val}\""
        if isinstance(val, bool):
            return "true" if val else "false"
        if val is None:
            return "null"
        return str(val)
    if isinstance(expr, ast_nodes.ListLiteral):
        return "[" + ", ".join(_render_expr(v) for v in expr.items) + "]"
    return str(expr)


def render_module_source(module: ast_nodes.Module) -> str:
    """Best-effort DSL-like renderer for expanded modules (debugging macros)."""
    lines: list[str] = []

    def indent(level: int, text: str) -> str:
        return "  " * level + text

    def render_flow_step(step: ast_nodes.FlowStepDecl, level: int) -> list[str]:
        step_lines = [indent(level, f'step is "{step.name}":')]
        step_lines.append(indent(level + 1, f'kind is "{step.kind}"'))
        if step.target:
            step_lines.append(indent(level + 1, f'target is "{step.target}"'))
        if step.message:
            step_lines.append(indent(level + 1, f'message is "{step.message}"'))
        params = getattr(step, "params", {}) or {}
        for key, val in params.items():
            if isinstance(val, ast_nodes.RecordQuery):
                step_lines.append(indent(level + 1, f"{key}: query alias={val.alias}"))
            else:
                step_lines.append(indent(level + 1, f"{key}: {_render_expr(val) or str(val)}"))
        for stmt in getattr(step, "statements", []) or []:
            if isinstance(stmt, ast_nodes.LogStatement):
                step_lines.append(indent(level + 1, f'log {stmt.level} "{stmt.message}"'))
            elif isinstance(stmt, ast_nodes.FlowAction):
                step_lines.append(indent(level + 1, f'do {stmt.kind} "{stmt.target}"'))
            else:
                step_lines.append(indent(level + 1, f"# {type(stmt).__name__}"))
        return step_lines

    for decl in module.declarations:
        if isinstance(decl, ast_nodes.FrameDecl):
            lines.append(f'frame is "{decl.name}":')
            lines.append("  source:")
            if decl.backend:
                lines.append(f'    backend is "{decl.backend}"')
            if decl.table:
                lines.append(f'    table is "{decl.table}"')
            if decl.url:
                lines.append(f"    url is {_render_expr(decl.url)}")
        elif isinstance(decl, ast_nodes.RecordDecl):
            lines.append(f'record is "{decl.name}":')
            lines.append(f'  frame is "{decl.frame}"')
            lines.append("  fields:")
            for field in decl.fields:
                lines.append(f"    {field.name}:")
                lines.append(f'      type is "{field.type}"')
                lines.append(f"      primary_key is {'true' if field.primary_key else 'false'}")
                lines.append(f"      required is {'true' if field.required else 'false'}")
                if field.default_expr is not None:
                    lines.append(f"      default is {_render_expr(field.default_expr)}")
                if field.numeric_min_expr is not None:
                    lines.append(f"      must be at least {_render_expr(field.numeric_min_expr)}")
                if field.numeric_max_expr is not None:
                    lines.append(f"      must be at most {_render_expr(field.numeric_max_expr)}")
        elif isinstance(decl, ast_nodes.FlowDecl):
            lines.append(f'flow is "{decl.name}":')
            for step in decl.steps:
                lines.extend(render_flow_step(step, 1))
        elif isinstance(decl, ast_nodes.PageDecl):
            route_part = f' at "{decl.route}"' if decl.route else ""
            lines.append(f'page is "{decl.name}"{route_part}:')
            if decl.sections:
                for section in decl.sections:
                    lines.append(indent(1, f'section is "{section.name}":'))
                    for child in section.layout:
                        lines.append(indent(2, f"{type(child).__name__}"))
        else:
            # Fallback: include repr for unhandled declarations
            name = getattr(decl, "name", None)
            if name:
                lines.append(f"# {type(decl).__name__}: {name}")
            else:
                lines.append(f"# {type(decl).__name__}")
    return "\n".join(lines) + ("\n" if lines else "")


def run_macro_tests(module: ast_nodes.Module, ai_callback: MacroCallback | None = None) -> tuple[list[str], list[str]]:
    """Run macro tests defined in a module. Returns (passed_tests, failures)."""
    macro_decls = [d for d in module.declarations if isinstance(d, ast_nodes.MacroDecl)]
    tests = [d for d in module.declarations if isinstance(d, ast_nodes.MacroTestDecl)]
    passed: list[str] = []
    failed: list[str] = []
    if not tests:
        return passed, failed
    for test in tests:
        expander = MacroExpander(ai_callback)
        try:
            expanded = expander.expand_module(ast_nodes.Module(declarations=macro_decls + list(test.uses)))
        except MacroExpansionError as exc:
            failed.append(f'{test.name}: macro expansion failed - {exc}')
            continue
        decls = expanded.declarations
        for expect in test.expects:
            kind = expect.kind.lower()
            name = expect.name
            ok = False
            if kind == "record":
                ok = any(isinstance(d, ast_nodes.RecordDecl) and d.name == name for d in decls)
            elif kind == "flow":
                ok = any(isinstance(d, ast_nodes.FlowDecl) and d.name == name for d in decls)
            elif kind == "page":
                ok = any(isinstance(d, ast_nodes.PageDecl) and d.name == name for d in decls)
            else:
                failed.append(f"{test.name}: unsupported expectation kind '{kind}'")
                continue
            if not ok:
                failed.append(f"{test.name}: expected {kind} \"{name}\" was not generated.")
        if not any(msg.startswith(f"{test.name}:") for msg in failed):
            passed.append(test.name)
    return passed, failed


def default_macro_ai_callback(macro: ast_nodes.MacroDecl, args: Dict[str, Any]) -> str:
    raise MacroExpansionError(create_diagnostic("N3M-1200", message_kwargs={"name": macro.name}).message)
