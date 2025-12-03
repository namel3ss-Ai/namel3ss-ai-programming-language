"""
UI renderer that maps IR to runtime UI models.
"""

from __future__ import annotations

from typing import List

from ..ir import IRPage
from .models import UIComponent, UIPage, UISection
from .runtime import map_component
from .components import UIComponentInstance


class UIRenderer:
    def from_ir_page(self, page: IRPage) -> UIPage:
        sections: List[UISection] = []
        for sec_idx, section in enumerate(page.sections):
            ui_components = []
            for comp_idx, comp in enumerate(section.components):
                comp_id = f"{page.name}:{section.name}:{comp_idx}"
                ui_components.append(
                    UIComponent(
                        id=comp_id,
                        type=comp.type,
                        props=comp.props,
                    )
                )
            sections.append(UISection(name=section.name, components=ui_components))
        return UIPage(
            name=page.name,
            title=page.title,
            route=page.route,
            sections=sections,
        )

    def build_runtime_components(self, page: IRPage) -> List[UIComponentInstance]:
        instances: List[UIComponentInstance] = []
        for sec_idx, section in enumerate(page.sections):
            for comp_idx, comp in enumerate(section.components):
                comp_id = f"{page.name}:{section.name}:{comp_idx}"
                instances.append(map_component(comp_id, comp.type, comp.props, section.name, page.name))
        return instances
