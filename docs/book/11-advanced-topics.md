# Chapter 12 — Authentication & User Context

- **Auth config:** `auth:` with `user_record`, `id_field`, `identifier_field`, `password_hash_field`.
- **Steps:** `auth_register`, `auth_login`, `auth_logout`.
- **User root:** Access `user.id`, `user.email`, etc., inside flows and UI.

Example:
```ai
frame is "users":
  backend is "memory"
  table is "users"

record is "User":
  frame is "users"
  fields:
    id:
      type is "uuid"
      primary_key is true
      required is true
    email:
      type is "string"
      required is true
    password_hash:
      type is "string"
      required is true

auth:
  backend is "default_auth"
  user_record is "User"
  id_field is "id"
  identifier_field is "email"
  password_hash_field is "password_hash"

flow is "register_user":
  step is "register":
    kind is "auth_register"
    input:
      email: state.email
      password: state.password

flow is "login_user":
  step is "login":
    kind is "auth_login"
    input:
      email: state.email
      password: state.password

flow is "logout_user":
  step is "logout":
    kind is "auth_logout"
```

Cross-reference: parser auth rules `src/namel3ss/parser.py`; runtime `src/namel3ss/runtime/auth.py`, context wiring `src/namel3ss/runtime/context.py`; tests `tests/test_auth.py`; example `examples/crud_app/crud_app.ai`.
