from __future__ import annotations

import importlib


def test_ir_imports_and_symbols() -> None:
    ir = importlib.import_module("namel3ss.ir")

    for name in [
        "IRApp",
        "IRPage",
        "IRModel",
        "IRAgent",
        "IRFlow",
        "IRFlowStep",
        "IRMemory",
        "IRTransactionBlock",
    ]:
        assert hasattr(ir, name), f"missing {name} export on namel3ss.ir"

    app = ir.IRApp(name="demo")
    assert app.name == "demo"

    flow = ir.IRFlow(name="sample", description=None)
    assert flow.steps == []
    assert flow.error_steps == []
