# Authentication & User Model (16A)

Namel3ss now has a first-class user model plus auth-aware flows.

## Declare a user record and auth config

```
record is "User":
  frame is "users"
  fields:
    id:
      type is "uuid"
      primary_key is true
    email:
      type is "string"
      required is true
    password_hash:
      type is "string"
      required is true

frame is "users":
  backend is "default_db"
  table is "users"

auth is:
  backend is "default_auth"
  user_record is "User"
  id_field is "id"
  identifier_field is "email"
  password_hash_field is "password_hash"
```

`auth` ties login/registration to the `User` record. Fields must exist on the record and `id_field` must be its primary key.

## Auth flow steps

Register:

```
flow is "register_user":
  step is "register":
    kind is "auth_register"
    input:
      email: state.email
      password: state.password
```

Login:

```
flow is "login_user":
  step is "login":
    kind is "auth_login"
    input:
      email: state.email
      password: state.password

  step is "store":
    kind is "set"
    target is state.user
    value is step.login.output.user
```

Logout:

```
flow is "logout_user":
  step is "logout":
    kind is "auth_logout"
```

## Using `user` in flows

`user` is available in expressions and reflects the current session:

```
flow is "create_project":
  step is "create":
    kind is "db_create"
    record is "Project"
    values:
      owner_id: user.id
      name: state.name
```

After `auth_login`, `user.is_authenticated` is true, `user.id` is set, and `user.record` holds the user row. After `auth_logout`, `user.is_authenticated` is false and `user.id` is null.

Passwords are hashed automatically (PBKDF2) and never stored in plain text. Auth failures return structured outputs (e.g., `AUTH_USER_EXISTS`, `AUTH_INVALID_CREDENTIALS`).
