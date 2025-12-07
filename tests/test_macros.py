import pytest

from namel3ss import ast_nodes
from namel3ss.errors import Namel3ssError
from namel3ss.macros import MacroExpander, expand_macros
from namel3ss.parser import parse_source


def test_macro_decl_parsing():
  src = (
      'macro "greet" using ai "codegen":\n'
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
      'use macro "crud" with:\n'
      '  entity "Product"\n'
      "  fields [\"name\", \"price\"]\n"
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
      'macro "greet" using ai "codegen":\n'
      '  description "Generate greeting flow"\n'
      '\n'
      'use macro "greet"\n'
  )

  def ai_cb(macro, args):
      return (
          'flow "greet":\n'
          '  step "hi":\n'
          '    log info "hello"\n'
      )

  expanded = _expand(src, ai_cb)
  flows = [d for d in expanded.declarations if isinstance(d, ast_nodes.FlowDecl)]
  assert len(flows) == 1
  assert flows[0].name == "greet"


def test_macro_expansion_with_parameters():
  src = (
      'macro "crud" using ai "codegen":\n'
      '  description "Generate CRUD"\n'
      "  parameters entity, fields\n"
      '\n'
      'use macro "crud" with:\n'
      '  entity "Product"\n'
      "  fields [\"name\", \"price\"]\n"
  )

  def ai_cb(macro, args):
      assert args["entity"] == "Product"
      assert args["fields"] == ["name", "price"]
      return (
          'flow "product_flow":\n'
          '  step "s":\n'
          '    log info "ok"\n'
      )

  expanded = _expand(src, ai_cb)
  assert any(isinstance(d, ast_nodes.FlowDecl) and d.name == "product_flow" for d in expanded.declarations)


def test_macro_missing_macro_raises():
  src = 'use macro "missing"\n'
  module = parse_source(src)
  with pytest.raises(Namel3ssError):
      expand_macros(module, lambda m, a: "")


def test_macro_output_parse_error():
  src = (
      'macro "bad" using ai "codegen":\n'
      '  description "bad output"\n'
      '\n'
      'use macro "bad"\n'
  )

  def ai_cb(macro, args):
      return "```not code```"

  with pytest.raises(Namel3ssError):
      _expand(src, ai_cb)


def test_macro_name_conflict():
  src = (
      'macro "m" using ai "codegen":\n'
      '  description "dup"\n'
      '\n'
      'use macro "m"\n'
      '\n'
      'flow "greet":\n'
      '  step "s":\n'
      '    log info "hi"\n'
  )

  def ai_cb(macro, args):
      return (
          'flow "greet":\n'
          '  step "s":\n'
          '    log info "hello"\n'
      )

  with pytest.raises(Namel3ssError):
      _expand(src, ai_cb)


def test_macro_expansion_too_large():
  src = (
      'macro "big" using ai "codegen":\n'
      '  description "big"\n'
      '\n'
      'use macro "big"\n'
  )

  def ai_cb(macro, args):
      return "flow \"x\":\n  step \"s\":\n    log info \"hi\"\n" + ("x" * 2100)

  with pytest.raises(Namel3ssError):
      _expand(src, ai_cb)


def test_macro_recursion_detected():
  src = (
      'macro "loop" using ai "codegen":\n'
      '  description "recurse"\n'
      '\n'
      'use macro "loop"\n'
  )

  def ai_cb(macro, args):
      return 'use macro "loop"\n'

  with pytest.raises(Namel3ssError):
      _expand(src, ai_cb)
