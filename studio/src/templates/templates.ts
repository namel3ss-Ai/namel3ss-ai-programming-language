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
    content: `app is "Simple App":
  starts at page "main"
  description "Minimal page with a welcome message."

page is "main":
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

ai is "rewrite_query":
  when called:
    use model "retriever"
    input comes from user_input
    describe task as "Rewrite the query to be concise and retrieval-friendly."

ai is "fetch_context":
  when called:
    use model "retriever"
    input comes from user_input
    describe task as "Identify relevant snippets for the rewritten query."

ai is "compose_answer":
  when called:
    use model "retriever"
    input comes from user_input
    describe task as "Compose a short answer based on retrieved snippets."

flow is "search_pipeline":
  description "Rewrite the query, retrieve context, and compose an answer."
  this flow will:
    first step "rewrite":
      do ai "rewrite_query"
    then step "retrieve":
      do ai "fetch_context"
    finally step "answer":
      do ai "compose_answer"

app is "RAG Demo":
  starts at page "search"
  description "RAG-flavored pipeline answering questions over a small note."

page is "search":
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

agent is "helper":
  the goal is "Offer concise, useful replies to user questions."
  the personality is "friendly and direct"

ai is "echo_intent":
  when called:
    use model "helper-llm"
    input comes from user_input
    describe task as "Restate the user's request to clarify intent."

flow is "ask_helper":
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

agent is "pro_agent":
  the goal is "Argue in favor of the topic with concise reasoning."
  the personality is "optimistic and evidence-focused"

agent is "con_agent":
  the goal is "Argue against the topic highlighting risks or gaps."
  the personality is "skeptical and pragmatic"

agent is "judge_agent":
  the goal is "Listen to both sides and deliver a balanced verdict."
  the personality is "neutral and structured"

flow is "debate_flow":
  description "Coordinate a short debate with pro, con, and judge roles."
  this flow will:
    first step "pro_turn":
      do agent "pro_agent"
    then step "con_turn":
      do agent "con_agent"
    finally step "judge_verdict":
      do agent "judge_agent"

app is "debate_app":
  starts at page "debate"
  description "Multi-agent debate system with a judge rendering verdicts."

page is "debate":
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

ai is "rewrite_query":
  when called:
    use model "retriever"
    input comes from user_input
    describe task as "Rewrite the query to be concise and retrieval-friendly."

ai is "fetch_context":
  when called:
    use model "retriever"
    input comes from user_input
    describe task as "Identify relevant snippets for the rewritten query."

ai is "compose_answer":
  when called:
    use model "retriever"
    input comes from user_input
    describe task as "Compose a short answer based on retrieved snippets."

flow is "rag_query_flow":
  description "Rewrite the query, retrieve context, and compose an answer."
  this flow will:
    first step "rewrite":
      do ai "rewrite_query"
    then step "retrieve":
      do ai "fetch_context"
    finally step "compose":
      do ai "compose_answer"

app is "rag_search_app":
  starts at page "search"
  description "RAG pipeline answering questions over a small note."

page is "search":
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

ai is "classify_issue":
  when called:
    use model "support-llm"
    input comes from user_input
    describe task as "Classify the user's support request."

ai is "kb_reader":
  when called:
    use model "support-llm"
    input comes from user_input
    describe task as "Suggest a KB snippet or next action."

agent is "support_agent":
  the goal is "Assist users by classifying issues, retrieving KB snippets, and advising next steps."
  the personality is "reassuring and efficient"

flow is "support_flow":
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

app is "support_app":
  starts at page "support"
  description "AI support assistant with tool calls and KB lookup."

page is "support":
  found at route "/support"
  titled "Support Assistant"
  section "intro":
    show text:
      "Run support_flow to categorize tickets, check status, and suggest resolutions."`,
  },
  {
    id: "cf-if-else",
    name: "Control Flow: If / Else",
    description: "English if / otherwise / else block.",
    filename: "control-flow-if.ai",
    category: "control-flow",
    content: `flow is "eligibility":
  step is "decide":
    let score be input.score

    if score is greater than 80:
      set state.status be "approved"
    otherwise if score is greater than 60:
      set state.status be "review"
    else:
      set state.status be "rejected"`,
  },
  {
    id: "cf-match",
    name: "Control Flow: Match",
    description: "Literal match/when/otherwise routing.",
    filename: "control-flow-match.ai",
    category: "control-flow",
    content: `flow is "router":
  step is "route":
    match state.intent:
      when "billing":
        set state.route be "billing_agent"
      when "technical":
        set state.route be "technical_agent"
      otherwise:
        set state.route be "general_agent"`,
  },
  {
    id: "cf-guard",
    name: "Control Flow: Guard",
    description: "Precondition guard that runs only when the condition is false.",
    filename: "control-flow-guard.ai",
    category: "control-flow",
    content: `flow is "checkout":
  step is "validate":
    guard state.is_authenticated is true:
      set state.error be "not_authenticated"
      return

    set state.status be "ok"`,
  },
  {
    id: "cf-repeat-for-each",
    name: "Control Flow: Repeat For Each",
    description: "Script-level loop over a list.",
    filename: "control-flow-repeat-for-each.ai",
    category: "control-flow",
    content: `flow is "process_items":
  step is "sum":
    let items be [1, 2, 3]
    let total be 0

    repeat for each item in items:
      set total be total + item

    set state.total be total`,
  },
  {
    id: "cf-repeat-up-to",
    name: "Control Flow: Repeat Up To",
    description: "Bounded repetition with a counter.",
    filename: "control-flow-repeat-up-to.ai",
    category: "control-flow",
    content: `flow is "bounded":
  step is "count":
    let attempts be 0

    repeat up to 3 times:
      set attempts be attempts + 1

    set state.attempts be attempts`,
  },
  {
    id: "cf-flow-for-each",
    name: "Control Flow: Flow-Level For Each",
    description: "Fan-out steps across state.items.",
    filename: "control-flow-flow-foreach.ai",
    category: "control-flow",
    content: `flow is "fan_out":
  step is "init":
    set state.items be [1, 2]

  for each item in state.items:
    step is "dispatch":
      kind is "tool"
      target is "echo"
      message is item`,
  },
  {
    id: "cf-retry",
    name: "Control Flow: Retry",
    description: "Retry up to N times with optional backoff.",
    filename: "control-flow-retry.ai",
    category: "control-flow",
    content: `flow is "call_api":
  step is "call":
    retry up to 3 times with backoff:
      do tool "echo"`,
  },
  {
    id: "cf-on-error",
    name: "Control Flow: On Error",
    description: "Flow-level error handler.",
    filename: "control-flow-on-error.ai",
    category: "control-flow",
    content: `flow is "with_fallback":
  step is "primary":
    kind is "tool"
    target is "unstable_tool"

  on error:
    step is "fallback":
      set state.error_handled be true`,
  },
  {
    id: "pipeline-filter",
    name: "Collection Pipeline (Filter)",
    description: "Filter a collection with keep/drop, ready to sort/take/skip.",
    filename: "pipeline-filter.ai",
    category: "snippets",
    content: `let filtered be SOURCE:
  keep rows where row.FIELD is "VALUE"
  # drop rows where row.should_skip is true
  # sort rows by row.FIELD descending
  # take first 10`,
  },
  {
    id: "pipeline-group-agg",
    name: "Pipeline with Group & Aggregates",
    description: "Group by a key and compute aggregates over rows.",
    filename: "pipeline-group-agg.ai",
    category: "snippets",
    content: `let summary be SOURCE:
  group by row.customer_id:
    let total_spent be sum of row.amount
    let orders_count be count of rows
    let avg_order_value be mean of row.amount
  sort groups by total_spent descending
  take first 10`,
  },
  {
    id: "find-active-users",
    name: "Find Active Users",
    description: "Query records with filters, ordering, and pagination.",
    filename: "find-active-users.ai",
    category: "snippets",
    content: `step is "list_active_users":
  find users where:
    is_active is true

  order users by created_at descending, name ascending
  limit users to 20`,
  },
  {
    id: "find-orders-status-country",
    name: "Find Orders by Status & Country",
    description: "Filter orders with English WHERE and sort by recency.",
    filename: "find-orders-status-country.ai",
    category: "snippets",
    content: `step is "list_orders":
  find orders where:
    status is "open"
    country is "BE"

  order orders by created_at descending
  limit orders to 50`,
  },
  {
    id: "record-safe-get",
    name: "Safe Record Access",
    description: "Access a record field with a default when missing.",
    filename: "record-safe-get.ai",
    category: "snippets",
    content: `let email be get user.email otherwise "unknown"
let has_vat be has key "vat_number" on user`,
  },
  {
    id: "loop-destructure-records",
    name: "Loop with Record Destructuring",
    description: "Iterate records and bind fields directly.",
    filename: "loop-destructure-records.ai",
    category: "snippets",
    content: `repeat for each { name, total } in records:
  log info "Record" with { name: name, total: total }`,
  },
  {
    id: "list-helpers",
    name: "List Helpers",
    description: "Pure list utilities: append, remove, insert.",
    filename: "list-helpers.ai",
    category: "snippets",
    content: `let ys be append xs with VALUE
let zs be remove VALUE from xs
let ws be insert VALUE at 0 into xs`,
  },
];
