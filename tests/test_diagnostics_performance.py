import time

from namel3ss import ir
from namel3ss.parser import parse_source
from namel3ss.lang.validator import validate_module
from namel3ss.diagnostics.pipeline import run_diagnostics


PROGRAM = (
    'app "support":\n'
    '  entry_page "home"\n'
    'page "home":\n'
    '  route "/"\n'
    'model "default":\n'
    '  provider "openai:gpt-4.1-mini"\n'
    'ai "summarise":\n'
    '  model "default"\n'
    '  input from user_message\n'
)


def test_diagnostics_performance_small_program():
    program = ir.ast_to_ir(parse_source(PROGRAM))
    start = time.perf_counter()
    for _ in range(10):
        run_diagnostics(program, available_plugins=set())
        validate_module(program)
    duration = time.perf_counter() - start
    avg = duration / 10.0
    assert avg < 0.01  # ~10ms per run budget for small programs
