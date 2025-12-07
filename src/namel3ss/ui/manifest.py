from __future__ import annotations

import hashlib
from typing import Any, Dict, List

from .. import ast_nodes
from ..ir import (
    IRLayoutElement,
    IRPage,
    IRProgram,
    IRHeading,
    IRText,
    IRImage,
    IREmbedForm,
    IRSection,
    IRUIInput,
    IRUIButton,
    IRUIConditional,
    IRUIShowBlock,
    IRUIEventAction,
    IRUIStyle,
    IRUIComponent,
    IRUIComponentCall,
)


def _styles(styles: List[IRUIStyle]) -> list[dict[str, Any]]:
    return [{"kind": s.kind, "value": s.value} for s in styles]


def _actions(actions: List[IRUIEventAction], program: IRProgram | None = None) -> list[dict[str, Any]]:
    formatted: list[dict[str, Any]] = []
    for a in actions:
        args: dict[str, Any] = {}
        for key, val in (a.args or {}).items():
            if isinstance(val, ast_nodes.Identifier):
                args[key] = {"identifier": val.name}
            elif isinstance(val, ast_nodes.StrLiteral):
                args[key] = {"literal": val.value}
            elif isinstance(val, ast_nodes.NumberLiteral):
                args[key] = {"literal": val.value}
            else:
                args[key] = {"expr": True}
        data = {"kind": a.kind, "target": a.target, "args": args}
        if a.kind == "goto_page" and program:
            target_page = program.pages.get(a.target)
            route = target_page.route if target_page and target_page.route else f"/{a.target}"
            data["route"] = route
        formatted.append(data)
    return formatted


def _make_element_id(signature: str, registry: dict[str, int]) -> str:
    registry[signature] = registry.get(signature, 0) + 1
    digest = hashlib.md5(signature.encode("utf-8")).hexdigest()[:8]
    return f"el_{digest}_{registry[signature]}"


def _layout(
    el: IRLayoutElement,
    id_registry: dict[str, int],
    program: IRProgram,
    source_path: str | None = None,
    parent_id: str | None = None,
    index: int = 0,
) -> dict[str, Any]:
    base_signature = f"{parent_id or 'root'}:{el.__class__.__name__}"
    key_value = None
    for attr in ("text", "label", "name", "url"):
        if hasattr(el, attr):
            key_value = getattr(el, attr)
            break
    if key_value is not None:
        base_signature = f"{base_signature}:{key_value}"
    el_id = _make_element_id(base_signature, id_registry)
    if isinstance(el, IRHeading):
        return {
            "type": "heading",
            "id": el_id,
            "parent_id": parent_id,
            "index": index,
            "text": el.text,
            "styles": _styles(getattr(el, "styles", [])),
            "source_path": source_path,
            "property_map": {"text": {"value": el.text}},
        }
    if isinstance(el, IRText):
        data = {
            "type": "text",
            "id": el_id,
            "parent_id": parent_id,
            "index": index,
            "text": el.text,
            "styles": _styles(getattr(el, "styles", [])),
        }
        if getattr(el, "expr", None) is not None:
            data["expr"] = True
        return data
    if isinstance(el, IRImage):
        return {
            "type": "image",
            "id": el_id,
            "parent_id": parent_id,
            "index": index,
            "url": el.url,
            "styles": _styles(getattr(el, "styles", [])),
        }
    if isinstance(el, IREmbedForm):
        return {
            "type": "form",
            "id": el_id,
            "parent_id": parent_id,
            "index": index,
            "form_name": el.form_name,
            "styles": _styles(getattr(el, "styles", [])),
        }
    if isinstance(el, IRUIInput):
        return {
            "type": "input",
            "id": el_id,
            "parent_id": parent_id,
            "index": index,
            "label": el.label,
            "name": el.var_name,
            "field_type": el.field_type,
            "styles": _styles(getattr(el, "styles", [])),
            "source_path": source_path,
            "property_map": {"label": {"value": el.label}},
        }
    if isinstance(el, IRUIButton):
        return {
            "type": "button",
            "id": el_id,
            "parent_id": parent_id,
            "index": index,
            "label": el.label,
            "actions": _actions(el.actions, program=program),
            "styles": _styles(getattr(el, "styles", [])),
            "source_path": source_path,
            "property_map": {"label": {"value": el.label}},
        }
    if isinstance(el, IRUIConditional):
        return {
            "type": "conditional",
            "id": el_id,
            "parent_id": parent_id,
            "index": index,
            "condition": True,
            "when": [
                _layout(child, id_registry, program, source_path=source_path, parent_id=el_id, index=i)
                for i, child in enumerate(el.when_block.layout if isinstance(el.when_block, IRUIShowBlock) else [])
            ],
            "otherwise": [
                _layout(child, id_registry, program, source_path=source_path, parent_id=el_id, index=i)
                for i, child in enumerate(el.otherwise_block.layout if isinstance(el.otherwise_block, IRUIShowBlock) else [])
            ],
            "source_path": source_path,
        }
    if isinstance(el, IRSection):
        return {
            "type": "section",
            "id": el_id,
            "parent_id": parent_id,
            "index": index,
            "name": el.name,
            "layout": [
                _layout(child, id_registry, program, source_path=source_path, parent_id=el_id, index=i)
                for i, child in enumerate(el.layout)
            ],
            "styles": _styles(getattr(el, "styles", [])),
            "source_path": source_path,
        }
    if isinstance(el, IRUIComponentCall):
        return {
            "type": "component_call",
            "id": el_id,
            "parent_id": parent_id,
            "index": index,
            "name": el.name,
            "styles": _styles(getattr(el, "styles", [])),
        }
    return {}


def _page_manifest(
    page: IRPage, id_registry: dict[str, int], program: IRProgram, source_path: str | None = None
) -> dict[str, Any]:
    route = page.route or f"/{page.name}"
    return {
        "name": page.name,
        "id": f"page_{page.name}",
        "route": route,
        "layout": [
            _layout(el, id_registry, program, source_path=source_path, parent_id=f"page_{page.name}", index=i)
            for i, el in enumerate(page.layout)
        ],
        "state": [{"name": st.name, "initial": st.initial} for st in getattr(page, "ui_states", [])],
        "styles": _styles(getattr(page, "styles", [])),
        "source_path": source_path,
    }


def build_ui_manifest(program: IRProgram) -> Dict[str, Any]:
    id_registry: dict[str, int] = {}
    pages = [_page_manifest(page, id_registry, program) for page in program.pages.values()]
    components: list[dict[str, Any]] = []
    for comp in program.ui_components.values():
        components.append(
            {
                "name": comp.name,
                "params": comp.params,
                "render": [
                    _layout(el, id_registry, program, parent_id=comp.name, index=i) for i, el in enumerate(comp.render)
                ],
                "styles": _styles(comp.styles),
            }
        )
    theme = {}
    if program.settings and program.settings.theme:
        theme = program.settings.theme
    return {
        "ui_manifest_version": "1",
        "pages": pages,
        "components": components,
        "theme": theme,
    }
