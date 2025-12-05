export interface Template {
  id: string;
  name: string;
  description: string;
  filename: string;
  category: string;
  content: string;
}

export const TEMPLATES: Template[] = [
  {
    id: "simple-app",
    name: "Simple App",
    description: "Minimal app with a single page and welcome text.",
    filename: "simple-app.ai",
    category: "examples",
    content: `app "Simple App":
  starts at page "main"
  description "Minimal page with a welcome message."

page "main":
  found at route "/"
  titled "Hello, Namel3ss"
  section "welcome":
    show text:
      "Welcome to your first app."`,
  },
  {
    id: "rag-example",
    name: "RAG Example",
    description: "Basic RAG-flavored pipeline that rewrites, retrieves, and answers.",
    filename: "rag-example.ai",
    category: "examples",
    content: `use model "retriever" provided by "openai"

ai "rewrite_query":
  when called:
    use model "retriever"
    input comes from user_input
    describe task as "Rewrite the query to be concise and retrieval-friendly."

ai "fetch_context":
  when called:
    use model "retriever"
    input comes from user_input
    describe task as "Identify relevant snippets for the rewritten query."

ai "compose_answer":
  when called:
    use model "retriever"
    input comes from user_input
    describe task as "Compose a short answer based on retrieved snippets."

flow "search_pipeline":
  description "Rewrite the query, retrieve context, and compose an answer."
  this flow will:
    first step "rewrite":
      do ai "rewrite_query"
    then step "retrieve":
      do ai "fetch_context"
    finally step "answer":
      do ai "compose_answer"

app "RAG Demo":
  starts at page "search"
  description "RAG-flavored pipeline answering questions over a small note."

page "search":
  found at route "/rag"
  titled "RAG Knowledge Search"
  section "query":
    show text:
      "Ask questions using search_pipeline to rewrite and answer."`,
  },
  {
    id: "agent-example",
    name: "Agent Example",
    description: "Minimal agent wired into a flow that calls it.",
    filename: "agent-example.ai",
    category: "examples",
    content: `use model "helper-llm" provided by "openai"

agent "helper":
  the goal is "Offer concise, useful replies to user questions."
  the personality is "friendly and direct"

ai "echo_intent":
  when called:
    use model "helper-llm"
    input comes from user_input
    describe task as "Restate the user's request to clarify intent."

flow "ask_helper":
  this flow will:
    first step "clarify":
      do ai "echo_intent"
    then step "respond":
      do agent "helper"`,
  },
  {
    id: "multi-agent-debate",
    name: "Multi-Agent Debate System",
    description: "Pro, Con, and Judge agents debate a topic with a final verdict.",
    filename: "multi-agent-debate.ai",
    category: "examples",
    content: `remember conversation as "debate_memory"

use model "debate-llm" provided by "openai"

agent "pro_agent":
  the goal is "Argue in favor of the topic with concise reasoning."
  the personality is "optimistic and evidence-focused"

agent "con_agent":
  the goal is "Argue against the topic highlighting risks or gaps."
  the personality is "skeptical and pragmatic"

agent "judge_agent":
  the goal is "Listen to both sides and deliver a balanced verdict."
  the personality is "neutral and structured"

flow "debate_flow":
  description "Coordinate a short debate with pro, con, and judge roles."
  this flow will:
    first step "pro_turn":
      do agent "pro_agent"
    then step "con_turn":
      do agent "con_agent"
    finally step "judge_verdict":
      do agent "judge_agent"

app "debate_app":
  starts at page "debate"
  description "Multi-agent debate system with a judge rendering verdicts."

page "debate":
  found at route "/debate"
  titled "Debate Console"
  section "context":
    show text:
      "Use debate_flow to run a structured pro/con discussion with a judge verdict."
  section "actions":
    show text:
      "Trigger debate_flow to start the conversation."`,
  },
  {
    id: "rag-search-app",
    name: "RAG Knowledge Search App",
    description: "RAG pipeline that rewrites queries, retrieves context, and composes answers.",
    filename: "rag-search-app.ai",
    category: "examples",
    content: `use model "retriever" provided by "openai"

ai "rewrite_query":
  when called:
    use model "retriever"
    input comes from user_input
    describe task as "Rewrite the query to be concise and retrieval-friendly."

ai "fetch_context":
  when called:
    use model "retriever"
    input comes from user_input
    describe task as "Identify relevant snippets for the rewritten query."

ai "compose_answer":
  when called:
    use model "retriever"
    input comes from user_input
    describe task as "Compose a short answer based on retrieved snippets."

flow "rag_query_flow":
  description "Rewrite the query, retrieve context, and compose an answer."
  this flow will:
    first step "rewrite":
      do ai "rewrite_query"
    then step "retrieve":
      do ai "fetch_context"
    finally step "compose":
      do ai "compose_answer"

app "rag_search_app":
  starts at page "search"
  description "RAG pipeline answering questions over a small note."

page "search":
  found at route "/rag"
  titled "RAG Knowledge Search"
  section "query":
    show text:
      "Ask questions against rag_query_flow to rewrite and answer."`,
  },
  {
    id: "support-agent",
    name: "AI Support Assistant",
    description: "Categorize support issues, call status tools, and answer with KB guidance.",
    filename: "support-agent.ai",
    category: "examples",
    content: `remember conversation as "support_memory"

use model "support-llm" provided by "openai"

ai "classify_issue":
  when called:
    use model "support-llm"
    input comes from user_input
    describe task as "Classify the user's support request."

ai "kb_reader":
  when called:
    use model "support-llm"
    input comes from user_input
    describe task as "Suggest a KB snippet or next action."

agent "support_agent":
  the goal is "Assist users by classifying issues, retrieving KB snippets, and advising next steps."
  the personality is "reassuring and efficient"

flow "support_flow":
  description "Classify the request, check ticket status, consult KB, and respond."
  this flow will:
    first step "categorize":
      do ai "classify_issue"
    then step "status_lookup":
      do tool "get_ticket_status" with message:
        "Lookup current ticket status."
    then step "kb_suggestion":
      do ai "kb_reader"
    finally step "respond":
      do agent "support_agent"

app "support_app":
  starts at page "support"
  description "AI support assistant with tool calls and KB lookup."

page "support":
  found at route "/support"
  titled "Support Assistant"
  section "intro":
    show text:
      "Run support_flow to categorize tickets, check status, and suggest resolutions."`,
  },
];
