from namel3ss import ast_nodes
from namel3ss.parser import parse_source


ENGLISH_PROGRAM = '''
remember conversation as "support_history"
use model "support-llm" provided by "openai"

ai "classify_issue":
  when called:
    use model "support-llm"
    input comes from user_input
    describe task as "Classify the user's support request."

agent "support_agent":
  the goal is "Provide a clear, helpful support answer."
  the personality is "patient, concise, calm"

flow "support_flow":
  this flow will:
    first step "classify request":
      do ai "classify_issue"
    then step "respond to user":
      do agent "support_agent"
    finally step "log interaction":
      do tool "echo" with message:
        "User request was processed and logged."

app "support_bot_app":
  starts at page "support_home"
  description "A simple support assistant with memory and classification."

page "support_home":
  found at route "/support"
  titled "Support Assistant"
  section "introduction":
    show text:
      "Welcome! Describe your issue and let the assistant help."
  section "chat":
    show form asking:
      "Describe your issue (login, billing, errors)."
'''


def test_parse_full_english_program():
  module = parse_source(ENGLISH_PROGRAM)
  assert isinstance(module, ast_nodes.Module)
  assert len(module.declarations) == 7

  memory = next(d for d in module.declarations if isinstance(d, ast_nodes.MemoryDecl))
  assert memory.name == "support_history"
  assert memory.memory_type == "conversation"

  model = next(d for d in module.declarations if isinstance(d, ast_nodes.ModelDecl))
  assert model.name == "support-llm"
  assert model.provider == "openai"

  ai_decl = next(d for d in module.declarations if isinstance(d, ast_nodes.AICallDecl))
  assert ai_decl.model_name == "support-llm"
  assert ai_decl.input_source == "user_input"
  assert ai_decl.description == "Classify the user's support request."

  agent = next(d for d in module.declarations if isinstance(d, ast_nodes.AgentDecl))
  assert agent.goal == "Provide a clear, helpful support answer."
  assert agent.personality == "patient, concise, calm"

  flow = next(d for d in module.declarations if isinstance(d, ast_nodes.FlowDecl))
  assert len(flow.steps) == 3
  assert [s.kind for s in flow.steps] == ["ai", "agent", "tool"]
  assert flow.steps[2].message == "User request was processed and logged."

  app = next(d for d in module.declarations if isinstance(d, ast_nodes.AppDecl))
  assert app.entry_page == "support_home"
  assert "classification" in (app.description or "")

  page = next(d for d in module.declarations if isinstance(d, ast_nodes.PageDecl))
  assert page.route == "/support"
  assert page.title == "Support Assistant"
  assert len(page.sections) == 2
  intro = page.sections[0]
  assert intro.components[0].type == "text"
  assert intro.components[0].props[0].value.startswith("Welcome!")
  chat = page.sections[1]
  assert chat.components[0].type == "form"
  assert "Describe your issue" in chat.components[0].props[0].value
