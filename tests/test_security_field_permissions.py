from namel3ss.security.context import SecurityContext
from namel3ss.security.fields import apply_field_permissions


FIELD_PERMISSIONS = {
    "MemoryRecord": {
        "content": "memory:content:read",
        "metadata": "memory:metadata:read_sensitive",
    }
}


def test_field_permissions_redact_without_permission():
    ctx = SecurityContext(subject_id="s", app_id=None, tenant_id=None, roles=["viewer"], scopes=[], auth_scheme="api_key")
    obj = {"content": "secret", "metadata": {"a": 1}, "other": "ok"}
    masked = apply_field_permissions(ctx, obj, "MemoryRecord", FIELD_PERMISSIONS)
    assert masked["content"] == "***redacted***"
    assert masked["metadata"] == "***redacted***"
    assert masked["other"] == "ok"


def test_field_permissions_allow_with_permission():
    ctx = SecurityContext(subject_id="s", app_id=None, tenant_id=None, roles=["admin"], scopes=[], auth_scheme="api_key")
    obj = {"content": "secret", "metadata": {"a": 1}}
    masked = apply_field_permissions(ctx, obj, "MemoryRecord", FIELD_PERMISSIONS)
    assert masked["content"] == "secret"
    assert masked["metadata"] == {"a": 1}
