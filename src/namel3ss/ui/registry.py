from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from ..ir import (
    IRPage,
    IRLayoutElement,
    IRSection,
    IRHeading,
    IRText,
    IRImage,
    IREmbedForm,
    IRUIInput,
    IRUIButton,
    IRUIConditional,
    IRUIShowBlock,
    IRUIComponentCall,
    IRUIStyle,
)


def _layout_to_dict(el: IRLayoutElement):
    if isinstance(el, IRHeading):
        return {"type": "heading", "text": el.text, "styles": _styles(el.styles)}
    if isinstance(el, IRText):
        data = {"type": "text", "text": el.text}
        if getattr(el, "expr", None) is not None:
            data["expr"] = True
        data["styles"] = _styles(el.styles)
        return data
    if isinstance(el, IRImage):
        return {"type": "image", "url": el.url, "styles": _styles(el.styles)}
    if isinstance(el, IREmbedForm):
        return {"type": "form", "form_name": el.form_name, "styles": _styles(el.styles)}
    if isinstance(el, IRUIInput):
        return {
            "type": "input",
            "label": el.label,
            "name": el.var_name,
            "field_type": el.field_type,
            "styles": _styles(el.styles),
        }
    if isinstance(el, IRUIButton):
        return {
            "type": "button",
            "label": el.label,
            "actions": [{"kind": a.kind, "target": a.target, "args": {k: True for k in a.args.keys()}} for a in el.actions],
            "styles": _styles(el.styles),
        }
    if isinstance(el, IRUIConditional):
        return {
            "type": "conditional",
            "condition": True,
            "when": [_layout_to_dict(child) for child in (el.when_block.layout if el.when_block else [])],
            "otherwise": [_layout_to_dict(child) for child in (el.otherwise_block.layout if el.otherwise_block else [])],
        }
    if isinstance(el, IRUIComponentCall):
        return {
            "type": "component_call",
            "name": el.name,
            "styles": _styles(el.styles),
        }
    if isinstance(el, IRSection):
        return {
            "type": "section",
            "name": el.name,
            "layout": [_layout_to_dict(child) for child in el.layout],
            "styles": _styles(el.styles),
        }
    return {}


def _styles(styles: list[IRUIStyle]):
    return [{"kind": s.kind, "value": s.value} for s in styles]


@dataclass
class UIPageRegistry:
    pages_by_name: Dict[str, IRPage] = field(default_factory=dict)
    pages_by_route: Dict[str, IRPage] = field(default_factory=dict)

    def register(self, page: IRPage):
        self.pages_by_name[page.name] = page
        if page.route:
            self.pages_by_route[page.route] = page

    def to_dict(self) -> dict:
        result: list[dict] = []
        for page in self.pages_by_name.values():
            result.append(
                {
                    "name": page.name,
                    "route": page.route,
                    "layout": [_layout_to_dict(el) for el in page.layout],
                    "state": [{"name": st.name, "initial": st.initial} for st in getattr(page, "ui_states", [])],
                    "styles": _styles(getattr(page, "styles", [])),
                }
            )
        return {"pages": result}
