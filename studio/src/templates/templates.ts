export interface Template {
  id: string;
  name: string;
  description: string;
  content: string;
}

export const TEMPLATES: Template[] = [
  {
    id: "simple-app",
    name: "Simple App",
    description: "Minimal app with a single page and welcome text.",
    content: `app "Simple App" {
  page main:
    title: "Hello, Namel3ss"
    section:
      text: "Welcome to your first app."
}`,
  },
  {
    id: "rag-example",
    name: "RAG Example",
    description: "Basic RAG pipeline using a dataset and search pipeline.",
    content: `app "RAG Demo" {
  dataset docs:
    # add your documents here

  rag_pipeline search_docs:
    from docs
    query input
}`,
  },
  {
    id: "agent-example",
    name: "Agent Example",
    description: "Minimal agent wired into a flow that calls it.",
    content: `agent helper {
  prompt:
    """
    You are a helpful assistant.
    """
}

flow ask_helper:
  input question
  step call_helper:
    use agent helper
    with question
}`,
  },
];
