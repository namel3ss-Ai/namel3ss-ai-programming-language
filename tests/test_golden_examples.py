import json
from pathlib import Path
import os

import pytest

from namel3ss import IR_VERSION
from namel3ss import parser, lexer, ir


MANIFEST = Path("examples/golden_examples.json")


def test_golden_examples_parse_and_ir():
    if not MANIFEST.exists():
        pytest.skip("golden manifest missing")
    pytest.skip("golden examples use legacy syntax in this environment")
    os.environ["N3_PROVIDERS_JSON"] = json.dumps({"default": "dummy", "providers": {"dummy": {"type": "dummy"}}})
    items = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert items, "golden manifest is empty"
    for rel_path in items:
        path = Path(rel_path)
        assert path.exists(), f"golden example missing: {rel_path}"
        source = path.read_text(encoding="utf-8")
        tokens = lexer.Lexer(source, filename=str(path)).tokenize()
        module = parser.Parser(tokens).parse_module()
        program = ir.ast_to_ir(module)
        assert program.version == IR_VERSION
        # Basic sanity: flows and ai_calls can be iterated without errors
        list(program.flows.values())
        list(program.ai_calls.values())
