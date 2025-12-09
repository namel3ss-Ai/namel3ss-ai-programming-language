# Auth boundary and user context

Namel3ss does **not** implement OAuth2, JWT validation, session storage, or RBAC enforcement. Those belong at the edge (API gateway/reverse proxy/web framework). A recommended pattern:

- A gateway (Kong, AWS API Gateway, Nginx + OIDC, Envoy, etc.) terminates TLS, validates JWT/OAuth, enforces rate limits/WAF, and injects user identity into headers or metadata.
- The Namel3ss runtime receives an already validated user context and uses it to drive flows/agents; it does not perform token validation itself.

## User context contract
- Expected shape: `{"id": "<user-id>|None", "is_authenticated": bool, "roles": [<strings>], "record": <optional user record>}`.
- Where it lives: `ExecutionContext.user_context` (and propagated into flow runtime context).
- Defaults: if not provided, Namel3ss uses `{"id": None, "is_authenticated": False, "roles": [], "record": None}`.
- Usage: flows/agents can read `state.context.get("user")` or `ExecutionContext.user_context` to branch logic, but should not attempt to validate credentials.

Keep authentication and authorization upstream; Namel3ss remains a stateless runtime behind that boundary.
