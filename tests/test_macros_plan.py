import pytest

from namel3ss import ast_nodes, parser
from namel3ss.macros import (
    AgentPlan,
    FlowPlan,
    MacroExpansionError,
    MacroExpander,
    MacroPlan,
    PagePlan,
    RagPipelinePlan,
    RagStagePlan,
    RecordFieldPlan,
    RecordPlan,
)


def test_macro_plan_validation_blocks_unknown_record():
    expander = MacroExpander(None)
    plan = MacroPlan(
        records=[RecordPlan(name="User")],
        flows=[FlowPlan(name="bad_flow", kind="list_crud", record="Missing")],
    )
    use = ast_nodes.MacroUse(macro_name="crud_ui", args={})
    with pytest.raises(MacroExpansionError):
        expander._expand_structured_plan(use, plan)


def test_macro_plan_expansion_emits_core_components():
    expander = MacroExpander(None)
    plan = MacroPlan(
        records=[RecordPlan(name="Item", fields=[RecordFieldPlan(name="name", type="string", required=True)])],
        flows=[FlowPlan(name="list_items", kind="list_crud", record="Item")],
        pages=[PagePlan(name="items_list", route="/items", kind="crud_list", record="Item")],
        rag_pipelines=[
            RagPipelinePlan(name="items_rag", stages=[RagStagePlan(name="vec", stage_type="vector_retrieve", params={"top_k": 3})])
        ],
        agents=[AgentPlan(name="item_agent", goal="Help users", model="gpt-4.1-mini", rag_pipeline="items_rag")],
    )
    use = ast_nodes.MacroUse(macro_name="app_scaffold", args={})
    module = expander._expand_structured_plan(use, plan)
    assert any(isinstance(d, ast_nodes.RecordDecl) and d.name == "Item" for d in module.declarations)
    assert any(isinstance(d, ast_nodes.FlowDecl) and d.name == "list_items" for d in module.declarations)
    assert any(isinstance(d, ast_nodes.PageDecl) and d.name == "items_list" for d in module.declarations)
    assert any(isinstance(d, ast_nodes.RagPipelineDecl) and d.name == "items_rag" for d in module.declarations)
    assert any(isinstance(d, ast_nodes.AgentDecl) and d.name == "item_agent" for d in module.declarations)


def test_macro_decl_version_parses():
    code = (
        'macro is "helper" using ai "codegen":\n'
        '  description "macro with version"\n'
        '  version is "2.0"\n'
    )
    module = parser.parse_source(code)
    macro = next(d for d in module.declarations if isinstance(d, ast_nodes.MacroDecl))
    assert macro.version == "2.0"
