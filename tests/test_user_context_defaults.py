from namel3ss.runtime.context import ExecutionContext, get_user_context


def test_execution_context_user_context_defaults():
    ctx = ExecutionContext(app_name="app", request_id="req")
    user_ctx = get_user_context(ctx.user_context)
    assert user_ctx["id"] is None
    assert user_ctx["is_authenticated"] is False
    assert user_ctx["roles"] == []
    assert "record" in user_ctx

