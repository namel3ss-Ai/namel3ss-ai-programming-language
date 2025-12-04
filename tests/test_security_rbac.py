from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from namel3ss.security.context import SecurityContext
from namel3ss.security.rbac import require_permissions


def test_require_permissions_allows_with_role():
    app = FastAPI()
    fake_ctx = SecurityContext(subject_id="s", app_id=None, tenant_id=None, roles=["developer"], scopes=[], auth_scheme="api_key")

    def ctx_dep():
        return fake_ctx

    @app.get("/ok")
    def ok(_ctx: SecurityContext = Depends(require_permissions(["flows:read"]))):
        return {"ok": True}

    # override auth dependency
    from namel3ss.security.oauth import get_oauth_context

    app.dependency_overrides[get_oauth_context] = ctx_dep
    client = TestClient(app)
    res = client.get("/ok")
    assert res.status_code == 200


def test_require_permissions_denies_without_role():
    app = FastAPI()
    fake_ctx = SecurityContext(subject_id="s", app_id=None, tenant_id=None, roles=["viewer"], scopes=[], auth_scheme="api_key")

    def ctx_dep():
        return fake_ctx

    @app.get("/forbid")
    def forbid(_ctx: SecurityContext = Depends(require_permissions(["memory:write"]))):
        return {"ok": True}

    from namel3ss.security.oauth import get_oauth_context

    app.dependency_overrides[get_oauth_context] = ctx_dep
    client = TestClient(app)
    res = client.get("/forbid")
    assert res.status_code == 403
