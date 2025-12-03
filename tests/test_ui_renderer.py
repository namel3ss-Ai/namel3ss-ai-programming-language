from namel3ss.ir import IRComponent, IRPage, IRSection
from namel3ss.ui.renderer import UIRenderer


def test_ui_renderer_maps_sections_and_components():
    ir_page = IRPage(
        name="home",
        title="Home",
        route="/",
        sections=[
            IRSection(
                name="hero",
                components=[
                    IRComponent(type="text", props={"value": "Welcome", "variant": "heading"})
                ],
            )
        ],
    )
    renderer = UIRenderer()
    ui_page = renderer.from_ir_page(ir_page)
    assert ui_page.name == "home"
    assert ui_page.sections[0].name == "hero"
    comp = ui_page.sections[0].components[0]
    assert comp.type == "text"
    assert comp.props["value"] == "Welcome"
