from namel3ss.version import __version__, IR_VERSION
from namel3ss import ir


def test_version_constants_present():
    assert isinstance(__version__, str) and __version__
    assert isinstance(IR_VERSION, str) and IR_VERSION


def test_ir_program_stamps_version():
    program = ir.IRProgram()
    assert program.version == IR_VERSION
