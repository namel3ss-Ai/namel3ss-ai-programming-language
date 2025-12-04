"""
Minimal OAuth2/OIDC helpers with pluggable verification.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

from fastapi import Depends, Header, HTTPException

from .context import SecurityContext


@dataclass
class OAuthConfig:
    issuer: str = ""
    audience: str = ""
    jwks_url: str = ""
    enabled: bool = False
    verify_signature: bool = False


API_KEY_HEADER = "X-API-Key"
API_KEY_ROLES = {
    "admin-key": ["admin"],
    "dev-key": ["developer"],
    "viewer-key": ["viewer"],
}


def _decode_jwt_no_verify(token: str) -> Dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("invalid token format")
    payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
    payload_bytes = base64.urlsafe_b64decode(payload_b64)
    return json.loads(payload_bytes.decode("utf-8"))


def parse_fake_token(token: str) -> Dict[str, Any]:
    """
    Deterministic parser for tests: tokens may be raw JSON or JWT-like.
    """
    try:
        return json.loads(token)
    except Exception:
        return _decode_jwt_no_verify(token)


def build_security_context(
    claims: Dict[str, Any], auth_scheme: str = "oauth2", api_key: Optional[str] = None
) -> SecurityContext:
    subject = claims.get("sub") or claims.get("subject")
    tenant = claims.get("tid") or claims.get("tenant")
    app_id = claims.get("azp") or claims.get("client_id") or claims.get("app")
    roles = claims.get("roles") or claims.get("role") or claims.get("groups") or []
    if isinstance(roles, str):
        roles = [roles]
    scopes_raw = claims.get("scope") or claims.get("scopes") or []
    if isinstance(scopes_raw, str):
        scopes = scopes_raw.split()
    else:
        scopes = list(scopes_raw)
    return SecurityContext(
        subject_id=subject,
        app_id=app_id,
        tenant_id=tenant,
        roles=roles,
        scopes=scopes,
        auth_scheme=auth_scheme if api_key is None else "api_key",
    )


def get_oauth_context(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
    config: OAuthConfig = Depends(lambda: OAuthConfig()),
) -> SecurityContext:
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
        if not config.enabled:
            claims = parse_fake_token(token)
            return build_security_context(claims, auth_scheme="oauth2")
        try:
            claims = parse_fake_token(token)
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid token")
        # basic audience/issuer hints when provided
        if config.audience and claims.get("aud") and claims.get("aud") != config.audience:
            raise HTTPException(status_code=401, detail="Invalid audience")
        if config.issuer and claims.get("iss") and claims.get("iss") != config.issuer:
            raise HTTPException(status_code=401, detail="Invalid issuer")
        return build_security_context(claims, auth_scheme="oauth2")

    if x_api_key:
        if x_api_key not in API_KEY_ROLES:
            raise HTTPException(status_code=401, detail="Invalid API key")
        roles = API_KEY_ROLES[x_api_key]
        return SecurityContext(
            subject_id=x_api_key,
            app_id=None,
            tenant_id=None,
            roles=roles,
            scopes=[],
            auth_scheme="api_key",
        )

    raise HTTPException(status_code=401, detail="Unauthorized")
