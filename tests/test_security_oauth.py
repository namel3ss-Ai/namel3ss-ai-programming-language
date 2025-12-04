from fastapi import Depends, FastAPI, Header
from fastapi.testclient import TestClient

from namel3ss.security.oauth import OAuthConfig, get_oauth_context
from namel3ss.security.context import SecurityContext


def build_app(config: OAuthConfig):
    app = FastAPI()

    def ctx_dep(
        authorization: str | None = Header(default=None),
        x_api_key: str | None = Header(default=None),
    ):
        return get_oauth_context(authorization=authorization, x_api_key=x_api_key, config=config)

    @app.get("/secure")
    def secure(ctx: SecurityContext = Depends(ctx_dep)):
        return {"subject": ctx.subject_id, "roles": ctx.roles, "scheme": ctx.auth_scheme}

    return app


def test_oauth_valid_token_builds_context():
    # token is base64-encoded JWT payload without verification
    payload = {"sub": "user1", "roles": ["developer"], "aud": "a1", "iss": "issuer"}
    import base64, json

    def make_token(claims):
        b = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
        return f"header.{b}.sig"

    token = make_token(payload)
    app = build_app(OAuthConfig(enabled=True, audience="a1", issuer="issuer"))
    client = TestClient(app)
    res = client.get("/secure", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["subject"] == "user1"
    assert data["roles"] == ["developer"]
    assert data["scheme"] == "oauth2"


def test_api_key_fallback_when_oauth_disabled():
    app = build_app(OAuthConfig(enabled=False))
    client = TestClient(app)
    res = client.get("/secure", headers={"X-API-Key": "dev-key"})
    assert res.status_code == 200
    data = res.json()
    assert data["roles"] == ["developer"]
    assert data["scheme"] == "api_key"
