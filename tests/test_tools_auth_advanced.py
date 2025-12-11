import json

from namel3ss.tools.registry import ToolAuthConfig
from namel3ss.tools.runtime import apply_auth_config, oauth_token_cache


def test_oauth2_client_credentials(monkeypatch):
    cfg = ToolAuthConfig(
        kind="oauth2_client_credentials",
        token_url="https://auth.example.com/token",
        client_id="client-id",
        client_secret="client-secret",
        scopes=["read"],
        cache="shared",
    )

    def fake_fetch(token_url, client_id, client_secret, scopes, audience):
        assert token_url.endswith("/token")
        return "FAKE_TOKEN", 100.0

    monkeypatch.setattr(oauth_token_cache, "_fetch_token", fake_fetch)
    url, headers = apply_auth_config(cfg, "https://api.example.com", {}, lambda x: x, "crm_api")
    assert url == "https://api.example.com"
    assert headers["Authorization"] == "Bearer FAKE_TOKEN"


def test_jwt_auth_hs256():
    cfg = ToolAuthConfig(
        kind="jwt",
        private_key="secret-key",
        issuer="issuer",
        subject="subject",
        audience="aud",
        algorithm="HS256",
    )
    _, headers = apply_auth_config(cfg, "https://example.com", {}, lambda x: x, "jwt_tool")
    assert "Authorization" in headers
    token = headers["Authorization"].split()[-1]
    # token should be a JWT with three segments
    assert token.count(".") == 2
