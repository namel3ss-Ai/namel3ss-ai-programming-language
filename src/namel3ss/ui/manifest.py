from __future__ import annotations

from typing import Any, Dict, List

from ..ir import (
    IRPage,
    IRProgram,
    IRLayoutElement,
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


def _actions(actions: List[IRUIEventAction]) -> list[dict[str, Any]]:
    return [{"kind": a.kind, "target": a.target, "args": a.args} for a in actions]


def _layout(el: IRLayoutElement) -> dict[str, Any]:
    if isinstance(el, IRHeading):
        return {"type": "heading", "text": el.text, "styles": _styles(getattr(el, "styles", []))}
    if isinstance(el, IRText):
        data = {
            "type": "text",
            "text": el.text,
            "styles": _styles(getattr(el, "styles", [])),
        }
        if getattr(el, "expr", None) is not None:
            data["expr"] = True
        return data
    if isinstance(el, IRImage):
        return {"type": "image", "url": el.url, "styles": _styles(getattr(el, "styles", []))}
    if isinstance(el, IREmbedForm):
        return {"type": "form", "form_name": el.form_name, "styles": _styles(getattr(el, "styles", []))}
    if isinstance(el, IRUIInput):
        return {
            "type": "input",
            "label": el.label,
            "name": el.var_name,
            "field_type": el.field_type,
            "styles": _styles(getattr(el, "styles", [])),
        }
    if isinstance(el, IRUIButton):
        return {
            "type": "button",
            "label": el.label,
            "actions": _actions(el.actions),
            "styles": _styles(getattr(el, "styles", [])),
        }
    if isinstance(el, IRUIConditional):
        return {
            "type": "conditional",
            "condition": True,
            "when": [_layout(child) for child in (el.when_block.layout if isinstance(el.when_block, IRUIShowBlock) else [])],
            "otherwise": [_layout(child) for child in (el.otherwise_block.layout if isinstance(el.otherwise_block, IRUIShowBlock) else [])],
        }
    if isinstance(el, IRSection):
        return {
            "type": "section",
            "name": el.name,
            "layout": [_layout(child) for child in el.layout],
            "styles": _styles(getattr(el, "styles", [])),
        }
    if isinstance(el, IRUIComponentCall):
        return {
            "type": "component_call",
            "name": el.name,
            "styles": _styles(getattr(el, "styles", [])),
        }
    return {}


def _page_manifest(page: IRPage) -> dict[str, Any]:
    return {
        "name": page.name,
        "route": page.route,
        "layout": [_layout(el) for el in page.layout],
        "state": [{"name": st.name, "initial": st.initial} for st in getattr(page, "ui_states", [])],
        "styles": _styles(getattr(page, "styles", [])),
    }


def build_ui_manifest(program: IRProgram) -> Dict[str, Any]:
    pages = [_page_manifest(page) for page in program.pages.values()]
    components: list[dict[str, Any]] = []
    for comp in program.ui_components.values():
        components.append(
            {
                "name": comp.name,
                "params": comp.params,
                "render": [_layout(el) for el in comp.render],
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
