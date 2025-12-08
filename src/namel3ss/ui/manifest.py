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
    IRCard,
    IRRow,
    IRColumn,
    IRTextarea,
    IRBadge,
    IRMessageList,
    IRMessage,
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
        if a.kind == "navigate":
            if a.target_path:
                data["targetPath"] = a.target_path
            if a.target_page:
                data["targetPage"] = a.target_page
                if program:
                    target_page = program.pages.get(a.target_page)
                    route = target_page.route if target_page and target_page.route else f"/{a.target_page}"
                    data["targetPath"] = data.get("targetPath") or route
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
    def _apply_styling(data: dict[str, Any], element: IRLayoutElement) -> dict[str, Any]:
        class_name = getattr(element, "class_name", None)
        if class_name:
            data["className"] = class_name
        style_map = getattr(element, "style", None)
        if isinstance(style_map, dict) and style_map:
            data["style"] = style_map
        return data

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
        data = {
            "type": "heading",
            "id": el_id,
            "parent_id": parent_id,
            "index": index,
            "text": el.text,
            "styles": _styles(getattr(el, "styles", [])),
            "source_path": source_path,
            "property_map": {"text": {"value": el.text}},
        }
        return _apply_styling(data, el)
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
        return _apply_styling(data, el)
    if isinstance(el, IRImage):
        data = {
            "type": "image",
            "id": el_id,
            "parent_id": parent_id,
            "index": index,
            "url": el.url,
            "styles": _styles(getattr(el, "styles", [])),
        }
        return _apply_styling(data, el)
    if isinstance(el, IREmbedForm):
        data = {
            "type": "form",
            "id": el_id,
            "parent_id": parent_id,
            "index": index,
            "form_name": el.form_name,
            "styles": _styles(getattr(el, "styles", [])),
        }
        return _apply_styling(data, el)
    if isinstance(el, IRCard):
        data = {
            "type": "card",
            "id": el_id,
            "parent_id": parent_id,
            "index": index,
            "title": el.title,
            "layout": [_layout(child, id_registry, program, source_path=source_path, parent_id=el_id, index=i) for i, child in enumerate(el.layout)],
            "styles": _styles(getattr(el, "styles", [])),
            "source_path": source_path,
        }
        return _apply_styling(data, el)
    if isinstance(el, IRRow):
        data = {
            "type": "row",
            "id": el_id,
            "parent_id": parent_id,
            "index": index,
            "layout": [_layout(child, id_registry, program, source_path=source_path, parent_id=el_id, index=i) for i, child in enumerate(el.layout)],
            "styles": _styles(getattr(el, "styles", [])),
            "source_path": source_path,
        }
        return _apply_styling(data, el)
    if isinstance(el, IRColumn):
        data = {
            "type": "column",
            "id": el_id,
            "parent_id": parent_id,
            "index": index,
            "layout": [_layout(child, id_registry, program, source_path=source_path, parent_id=el_id, index=i) for i, child in enumerate(el.layout)],
            "styles": _styles(getattr(el, "styles", [])),
            "source_path": source_path,
        }
        return _apply_styling(data, el)
    if isinstance(el, IRTextarea):
        data = {
            "type": "textarea",
            "id": el_id,
            "parent_id": parent_id,
            "index": index,
            "label": el.label,
            "name": el.var_name or el.label,
            "styles": _styles(getattr(el, "styles", [])),
            "source_path": source_path,
            "property_map": {"label": {"value": el.label}},
        }
        if el.var_name:
            data["binding"] = {"kind": "state", "path": el.var_name}
        if getattr(el, "validation", None):
            data["validation"] = {
                "required": el.validation.get("required"),
                "minLength": el.validation.get("min_length"),
                "maxLength": el.validation.get("max_length"),
                "pattern": el.validation.get("pattern"),
                "message": el.validation.get("message"),
            }
        return _apply_styling(data, el)
    if isinstance(el, IRBadge):
        data = {
            "type": "badge",
            "id": el_id,
            "parent_id": parent_id,
            "index": index,
            "text": el.text,
            "styles": _styles(getattr(el, "styles", [])),
            "source_path": source_path,
            "property_map": {"text": {"value": el.text}},
        }
        return _apply_styling(data, el)
    if isinstance(el, IRMessageList):
        data = {
            "type": "message_list",
            "id": el_id,
            "parent_id": parent_id,
            "index": index,
            "layout": [_layout(child, id_registry, program, source_path=source_path, parent_id=el_id, index=i) for i, child in enumerate(el.layout)],
            "styles": _styles(getattr(el, "styles", [])),
            "source_path": source_path,
        }
        return _apply_styling(data, el)
    if isinstance(el, IRMessage):
        data = {
            "type": "message",
            "id": el_id,
            "parent_id": parent_id,
            "index": index,
            "role": None,
            "text": None,
            "styles": _styles(getattr(el, "styles", [])),
            "source_path": source_path,
        }
        if el.role is None:
            data["role"] = None
        else:
            data["role"] = getattr(el.role, "value", None) if hasattr(el.role, "value") else None
            if data["role"] is None:
                data["role_expr"] = True
        if el.text_expr is None:
            data["text"] = None
        else:
            if hasattr(el.text_expr, "value"):
                data["text"] = el.text_expr.value
            else:
                data["text_expr"] = True
        if el.name:
            data["name"] = el.name
        return _apply_styling(data, el)
    if isinstance(el, IRUIInput):
        data = {
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
        if el.var_name:
            data["binding"] = {"kind": "state", "path": el.var_name}
        if getattr(el, "validation", None):
            data["validation"] = {
                "required": el.validation.get("required"),
                "minLength": el.validation.get("min_length"),
                "maxLength": el.validation.get("max_length"),
                "pattern": el.validation.get("pattern"),
                "message": el.validation.get("message"),
            }
        return _apply_styling(data, el)
    if isinstance(el, IRUIButton):
        button_data = {
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
        # Provide a premium onClick shape for navigation
        navigate = next((a for a in el.actions if a.kind == "navigate"), None)
        if navigate:
            target_info: dict[str, Any] = {"pageName": None, "path": None}
            if navigate.target_page:
                target_info["pageName"] = navigate.target_page
            if navigate.target_path:
                target_info["path"] = navigate.target_path
            if navigate.target_page and program:
                target_page = program.pages.get(navigate.target_page)
                route = target_page.route if target_page and target_page.route else f"/{navigate.target_page}"
                if target_info["path"] is None:
                    target_info["path"] = route
            nav_entry = {"kind": "navigate", "target": target_info}
            button_data["onClick"] = nav_entry
        return _apply_styling(button_data, el)
    if isinstance(el, IRUIConditional):
        data = {
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
        return _apply_styling(data, el)
    if isinstance(el, IRSection):
        data = {
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
        return _apply_styling(data, el)
    if isinstance(el, IRUIComponentCall):
        data = {
            "type": "component_call",
            "id": el_id,
            "parent_id": parent_id,
            "index": index,
            "name": el.name,
            "styles": _styles(getattr(el, "styles", [])),
        }
        return _apply_styling(data, el)
    return {}


def _page_manifest(
    page: IRPage, id_registry: dict[str, int], program: IRProgram, source_path: str | None = None
) -> dict[str, Any]:
    route = page.route or f"/{page.name}"
    data = {
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
    class_name = getattr(page, "class_name", None)
    if class_name:
        data["className"] = class_name
    style_map = getattr(page, "style", None)
    if isinstance(style_map, dict) and style_map:
        data["style"] = style_map
    return data


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
                "className": comp.class_name,
                "style": comp.style or {},
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
