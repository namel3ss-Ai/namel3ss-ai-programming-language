# Chapter 15 — Putting It All Together: End-to-End App

Combine auth, CRUD, memory, tools, and UI in one `.ai` file:

```ai
app is "support-suite":
  entry_page is "home"

model is "support-llm":
  provider is "openai_default"

ai is "support_ai":
  model is "support-llm"
  system is "Support bot that uses recall and knowledge base."
  tools:
    - "get_weather"
  memory:
    kinds:
      short_term:
        window is 6
    recall:
      - source is "short_term"
        count is 6

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

frame is "projects":
  backend is "memory"
  table is "projects"

record is "Project":
  frame is "projects"
  fields:
    id:
      type is "uuid"
      primary_key is true
      required is true
    owner_id:
      type is "string"
      required is true
    name:
      type is "string"
      required is true
    description:
      type is "text"

tool is "get_weather":
  kind is "http_json"
  method is "GET"
  url is "https://api.example.com/weather"
  query:
    city: input.city

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

flow is "create_project":
  step is "create":
    kind is "db_create"
    record is "Project"
    values:
      id: state.project_id
      owner_id: user.id
      name: state.project_name
      description: state.project_description

flow is "list_projects":
  step is "list":
    kind is "db_get"
    record is "Project"
    where:
      owner_id: user.id

flow is "ask_weather":
  step is "fetch":
    kind is "tool"
    target is "get_weather"
    input:
      city: state.city
  step is "respond":
    kind is "ai"
    target is "support_ai"

page is "home" at "/":
  section is "auth":
    input is "email":
      bind is state.email
    input is "password":
      bind is state.password
    button is "Register":
      on click:
        do flow "register_user"
    button is "Login":
      on click:
        do flow "login_user"
  section is "projects":
    input is "project_name":
      bind is state.project_name
    textarea is "project_description":
      bind is state.project_description
    button is "Create Project":
      on click:
        do flow "create_project"
    button is "Refresh List":
      on click:
        do flow "list_projects"
    text is "Projects: " + step.list.output
  section is "assistant":
    input is "city":
      bind is state.city
    button is "Ask Weather":
      on click:
        do flow "ask_weather"
    text is step.respond.output
```

Run flows with the CLI, then open Studio for interactive UI, traces, memory, and provider status. This pattern scales to richer assistants and dashboards by reusing the same building blocks.

Cross-reference: parser and runtime modules cited in prior chapters; tests across flows, memory, tools, auth, and UI; examples `examples/support_bot/support_bot.ai`, `examples/rag_qa/rag_qa.ai`, `examples/crud_app/crud_app.ai`, `examples/tools_and_ai/tools_and_ai.ai`.
