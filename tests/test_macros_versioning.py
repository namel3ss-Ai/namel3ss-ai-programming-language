from namel3ss.macros import MacroPlan, run_macro_migration


def test_macro_plan_default_version():
    plan = MacroPlan.from_raw({"records": []})
    assert plan.version == "1.0"


def test_run_macro_migration_reports_versions():
    message = run_macro_migration("crud_ui", "1.0", "1.1")
    assert "crud_ui" in message
    assert "1.1" in message
