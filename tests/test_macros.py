import pytest

from namel3ss import ast_nodes
from namel3ss.errors import Namel3ssError
from namel3ss.macros import MacroExpander, MacroExpansionError, expand_macros
from namel3ss.parser import parse_source


def test_macro_decl_parsing():
  src = (
      'macro is "greet" using ai "codegen":\n'
      '  description "Generate greeting flow"\n'
      '  sample "Example sample"\n'
      "  parameters name\n"
  )
  module = parse_source(src)
  macro = next(d for d in module.declarations if isinstance(d, ast_nodes.MacroDecl))
  assert macro.name == "greet"
  assert macro.ai_model == "codegen"
  assert macro.description.startswith("Generate")
  assert macro.sample.startswith("Example")
  assert macro.parameters == ["name"]


def test_macro_use_parsing_with_args():
  src = (
      'use macro is "crud" with:\n'
      '  entity is "Product"\n'
      "  fields are [\"name\", \"price\"]\n"
  )
  module = parse_source(src)
  use = next(d for d in module.declarations if isinstance(d, ast_nodes.MacroUse))
  assert use.macro_name == "crud"
  assert set(use.args.keys()) == {"entity", "fields"}


def _expand(src: str, ai_callback):
  module = parse_source(src)
  expander = MacroExpander(ai_callback)
  return expander.expand_module(module)


def test_macro_expansion_generates_flow():
  src = (
      'macro is "greet" using ai "codegen":\n'
      '  description "Generate greeting flow"\n'
      '\n'
      'use macro is "greet"\n'
  )

  def ai_cb(macro, args):
      return (
          'flow is "greet":\n'
          '  step is "hi":\n'
          '    log info "hello"\n'
      )

  expanded = _expand(src, ai_cb)
  flows = [d for d in expanded.declarations if isinstance(d, ast_nodes.FlowDecl)]
  assert len(flows) == 1
  assert flows[0].name == "greet"


def test_macro_expansion_with_parameters():
  src = (
      'macro is "crud" using ai "codegen":\n'
      '  description "Generate CRUD"\n'
      "  parameters entity, fields\n"
      '\n'
      'use macro is "crud" with:\n'
      '  entity is "Product"\n'
      "  fields are [\"name\", \"price\"]\n"
  )

  def ai_cb(macro, args):
      assert args["entity"] == "Product"
      assert args["fields"] == ["name", "price"]
      return (
          'flow is "product_flow":\n'
          '  step is "s":\n'
          '    log info "ok"\n'
      )

  expanded = _expand(src, ai_cb)
  assert any(isinstance(d, ast_nodes.FlowDecl) and d.name == "product_flow" for d in expanded.declarations)


def test_macro_missing_macro_raises():
  src = 'use macro is "missing"\n'
  module = parse_source(src)
  with pytest.raises(Namel3ssError):
      expand_macros(module, lambda m, a: "")


def test_macro_use_requires_is_in_args():
  src = (
      'use macro is "crud" with:\n'
      '  entity "Product"\n'
  )
  with pytest.raises(Exception) as excinfo:
      parse_source(src)
  assert "Expected 'is' after entity" in str(excinfo.value)


def test_macro_output_parse_error():
  src = (
      'macro is "bad" using ai "codegen":\n'
      '  description "bad output"\n'
      '\n'
      'use macro is "bad"\n'
  )

  def ai_cb(macro, args):
      return 'flow "legacy":\n  step is "s":\n    log info "hi"\n'

  with pytest.raises(MacroExpansionError) as excinfo:
      _expand(src, ai_cb)
  message = str(excinfo.value)
  assert 'Macro "bad"' in message
  assert 'flow "legacy": is not supported' in message
  assert "line" in message


def test_macro_name_conflict():
  src = (
      'macro is "m" using ai "codegen":\n'
      '  description "dup"\n'
      '\n'
      'use macro is "m"\n'
      '\n'
      'flow is "greet":\n'
      '  step is "s":\n'
      '    log info "hi"\n'
  )

  def ai_cb(macro, args):
      return (
          'flow is "greet":\n'
          '  step is "s":\n'
          '    log info "hello"\n'
      )

  with pytest.raises(Namel3ssError):
      _expand(src, ai_cb)


def test_macro_expansion_too_large():
  src = (
      'macro is "big" using ai "codegen":\n'
      '  description "big"\n'
      '\n'
      'use macro is "big"\n'
  )

  def ai_cb(macro, args):
      return 'flow is "x":\n  step is "s":\n    log info "hi"\n' + ("x" * 20000)

  with pytest.raises(MacroExpansionError) as excinfo:
      _expand(src, ai_cb)
  assert "Macro \"big\"" in str(excinfo.value)
  assert "limit" in str(excinfo.value) or "too large" in str(excinfo.value)


def test_macro_respects_configurable_limit(monkeypatch):
  src = (
      'macro is "big" using ai "codegen":\n'
      '  description "big"\n'
      '\n'
      'use macro is "big"\n'
  )
  monkeypatch.setenv("NAMEL3SS_MAX_MACRO_OUTPUT", "60")

  def ai_cb(macro, args):
      return 'flow is "x":\n  step is "s":\n    log info "hi"\n' + ("y" * 55)

  with pytest.raises(MacroExpansionError) as excinfo:
      _expand(src, ai_cb)
  assert "NAMEL3SS" not in str(excinfo.value)  # just ensure formatted message, not env name
  assert "Macro \"big\"" in str(excinfo.value)
  assert "limit" in str(excinfo.value)


def test_macro_under_limit_passes(monkeypatch):
  src = (
      'macro is "small" using ai "codegen":\n'
      '  description "small"\n'
      '\n'
      'use macro is "small"\n'
  )
  monkeypatch.setenv("NAMEL3SS_MAX_MACRO_OUTPUT", "200")

  def ai_cb(macro, args):
      return 'flow is "ok":\n  step is "s":\n    log info "fine"\n'

  expanded = _expand(src, ai_cb)
  flows = [d for d in expanded.declarations if isinstance(d, ast_nodes.FlowDecl)]
  assert flows and flows[0].name == "ok"


def test_macro_recursion_detected():
  src = (
      'macro is "loop" using ai "codegen":\n'
      '  description "recurse"\n'
      '\n'
      'use macro is "loop"\n'
  )

  def ai_cb(macro, args):
      return 'use macro is "loop"\n'

  with pytest.raises(MacroExpansionError):
      _expand(src, ai_cb)


def test_nested_macro_expansion():
  src = (
      'macro is "inner" using ai "codegen":\n'
      '  description "inner macro"\n'
      '  sample "flow is \\"inner_flow\\":\\n  step is \\"s\\":\\n    log info \\"inner\\""\n'
      '\n'
      'macro is "outer" using ai "codegen":\n'
      '  description "outer macro"\n'
      '  sample "use macro is \\"inner\\"\\nflow is \\"outer_flow\\":\\n  step is \\"s\\":\\n    log info \\"outer\\""\n'
      '\n'
      'use macro is "outer"\n'
  )
  module = parse_source(src)
  expanded = MacroExpander(None).expand_module(module)
  flows = {d.name for d in expanded.declarations if isinstance(d, ast_nodes.FlowDecl)}
  assert {"inner_flow", "outer_flow"} <= flows


def test_macro_cycle_reports_chain():
  src = (
      'macro is "A" using ai "codegen":\n'
      '  description "calls B"\n'
      '  sample "use macro is \\"B\\""\n'
      '\n'
      'macro is "B" using ai "codegen":\n'
      '  description "calls A"\n'
      '  sample "use macro is \\"A\\""\n'
      '\n'
      'use macro is "A"\n'
  )
  module = parse_source(src)
  with pytest.raises(MacroExpansionError) as excinfo:
      MacroExpander(None).expand_module(module)
  msg = str(excinfo.value)
  assert "Macro \"A\"" in msg
  assert "B" in msg
  assert "chain" in msg or "Recursive" in msg


def test_macro_backtick_error_message():
  src = (
      'macro is "ticks" using ai "codegen":\n'
      '  description "bad ticks"\n'
      '\n'
      'use macro is "ticks"\n'
  )

  def ai_cb(macro, args):
      return "```flow is \"x\":\n  step is \"s\":\n    log info \"hi\"```"

  with pytest.raises(MacroExpansionError) as excinfo:
      _expand(src, ai_cb)
  message = str(excinfo.value)
  assert 'Macro "ticks"' in message
  assert "backticks" in message.lower()


def test_template_macro_expands_without_ai():
  src = (
      'macro is "tmpl" using ai "codegen":\n'
      '  description "Template flow"\n'
      '  sample "flow is \\"{FlowName}\\":\\n  step is \\"start\\":\\n    log info \\"Hello, {name}\\""\n'
      '\n'
      'use macro is "tmpl" with:\n'
      '  FlowName is "welcome"\n'
      '  name is "Disan"\n'
  )
  module = parse_source(src)
  expander = MacroExpander(None)
  expanded = expander.expand_module(module)
  flows = [d for d in expanded.declarations if isinstance(d, ast_nodes.FlowDecl)]
  assert flows and flows[0].name == "welcome"
  stmt = flows[0].steps[0].statements[0]
  assert isinstance(stmt, ast_nodes.LogStatement)
  assert stmt.message == "Hello, Disan"


def test_template_fallback_when_ai_missing():
  src = (
      'macro is "tmpl" using ai "codegen":\n'
      '  description "Template flow"\n'
      '  sample "flow is \\"fallback\\":\\n  step is \\"s\\":\\n    log info \\"ok\\""\n'
      '\n'
      'use macro is "tmpl"\n'
  )
  expander = MacroExpander(None)
  expanded = _expand(src, lambda m, a: (_ for _ in ()).throw(MacroExpansionError("no ai")) )
  flows = [d for d in expanded.declarations if isinstance(d, ast_nodes.FlowDecl)]
  assert flows and flows[0].name == "fallback"


def test_macro_arg_expression_errors():
  src = (
      'macro is "tmpl" using ai "codegen":\n'
      '  description "Template flow"\n'
      '  sample "flow is \\"f\\":\\n  step is \\"s\\":\\n    log info \\"ok\\""\n'
      '\n'
      'use macro is "tmpl" with:\n'
      '  name is other_var\n'
  )
  module = parse_source(src)
  expander = MacroExpander(None)
  with pytest.raises(MacroExpansionError) as excinfo:
      expander.expand_module(module)
  msg = str(excinfo.value)
  assert 'Macro "tmpl"' in msg
  assert "literal values" in msg


def test_crud_ui_accepts_field_blocks():
  src = (
      'use macro is "crud_ui" with:\n'
      '  entity is "Product"\n'
      "  fields:\n"
      '    field is "name":\n'
      '      type is "string"\n'
      '      required is true\n'
      '    field is "price":\n'
      '      type is "float"\n'
      '      required is true\n'
      '      min is 0\n'
      '    field is "is_active":\n'
      '      type is "bool"\n'
      '      default is true\n'
  )
  module = parse_source(src)
  expander = MacroExpander(None)
  expanded = expander.expand_module(module)
  flows = [d for d in expanded.declarations if isinstance(d, ast_nodes.FlowDecl)]
  assert any(f.name == "create_product" for f in flows)
  assert any(f.name == "edit_product" for f in flows)
  code = "\n".join(f'{d.name}' for d in flows)
  assert "create_product" in code and "edit_product" in code


def test_crud_ui_generates_records_and_db_steps():
  src = (
      'use macro is "crud_ui" with:\n'
      '  entity is "Product"\n'
      "  fields:\n"
      '    field is "name":\n'
      '      type is "string"\n'
      '      required is true\n'
      '    field is "price":\n'
      '      type is "float"\n'
      '      required is true\n'
      '      min is 0\n'
  )
  module = parse_source(src)
  expanded = MacroExpander(None).expand_module(module)
  record = next(d for d in expanded.declarations if isinstance(d, ast_nodes.RecordDecl))
  assert record.name == "Product"
  assert record.frame == "products_frame"
  field_map = {f.name: f for f in record.fields}
  assert "product_id" in field_map and field_map["product_id"].primary_key is True
  assert "name" in field_map and field_map["name"].required is True
  flows = {d.name: d for d in expanded.declarations if isinstance(d, ast_nodes.FlowDecl)}
  assert {"list_products", "create_product", "edit_product", "delete_product"} <= set(flows.keys())
  create_step = flows["create_product"].steps[0]
  assert create_step.kind == "db_create"
  assert create_step.target == "Product"
  assert "values" in create_step.params
  list_step = flows["list_products"].steps[0]
  assert list_step.params.get("query")
