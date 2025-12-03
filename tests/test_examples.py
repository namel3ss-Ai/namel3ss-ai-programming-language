from pathlib import Path

from namel3ss import ir, lexer, parser
from namel3ss.runtime.engine import Engine


EXAMPLES = [
    Path("examples/getting_started/app.ai"),
    Path("examples/agents_and_flows/app.ai"),
    Path("examples/rag_search/app.ai"),
]


def parse_example(path: Path):
    src = path.read_text(encoding="utf-8")
    tokens = lexer.Lexer(src, filename=str(path)).tokenize()
    module = parser.Parser(tokens).parse_module()
    return ir.ast_to_ir(module)


def test_examples_parse_and_have_flows():
    for path in EXAMPLES:
        program = parse_example(path)
        assert program.flows


def test_basic_example_runs_flow(tmp_path):
    program = parse_example(EXAMPLES[0])
    engine = Engine(program)
    result = engine.execute_flow("pipeline")
    assert isinstance(result, dict)
    assert result.get("state") is not None
    assert result.get("flow_name") == "pipeline"
