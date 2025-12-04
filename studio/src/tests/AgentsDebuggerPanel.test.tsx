import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { vi } from "vitest";
import AgentsDebuggerPanel from "../panels/AgentsDebuggerPanel";
import { ApiClient } from "../api/client";

const fakeClient = {
  ...ApiClient,
  fetchAgentTraces: vi.fn(),
  fetchAgentTraceById: vi.fn(),
};

const sampleDetail = {
  id: "run-1",
  agent_name: "helper",
  started_at: new Date().toISOString(),
  finished_at: new Date().toISOString(),
  status: "completed",
  duration_seconds: 1.1,
  steps: [
    {
      id: "s1",
      step_name: "plan",
      kind: "plan",
      target: null,
      started_at: new Date().toISOString(),
      finished_at: new Date().toISOString(),
      success: true,
      retries: 0,
      tool_calls: [],
      memory_events: [],
      rag_events: [],
    },
    {
      id: "s2",
      step_name: "act",
      kind: "ai",
      target: "summarise",
      started_at: new Date().toISOString(),
      finished_at: new Date().toISOString(),
      success: true,
      retries: 0,
      tool_calls: [],
      memory_events: [],
      rag_events: [],
    },
  ],
  messages: [
    {
      id: "m1",
      role: "planner",
      content_preview: "Plan step",
      timestamp: new Date().toISOString(),
      related_step_id: "s1",
    },
  ],
};

describe("AgentsDebuggerPanel", () => {
  it("renders empty state when no traces", async () => {
    (fakeClient.fetchAgentTraces as any).mockResolvedValueOnce([]);
    render(<AgentsDebuggerPanel client={fakeClient} />);
    expect(await screen.findByText("No agent runs yet.")).toBeInTheDocument();
  });

  it("loads and displays agent trace tabs", async () => {
    (fakeClient.fetchAgentTraces as any).mockResolvedValue([{ id: "run-1", agent_name: "helper", started_at: new Date().toISOString() }]);
    (fakeClient.fetchAgentTraceById as any).mockResolvedValue(sampleDetail);
    render(<AgentsDebuggerPanel client={fakeClient} />);
    await waitFor(() => expect(fakeClient.fetchAgentTraces).toHaveBeenCalled());
    expect(await screen.findByText("helper")).toBeInTheDocument();
  });

  it("selecting timeline steps updates details", async () => {
    (fakeClient.fetchAgentTraces as any).mockResolvedValue([{ id: "run-1", agent_name: "helper", started_at: new Date().toISOString() }]);
    (fakeClient.fetchAgentTraceById as any).mockResolvedValue(sampleDetail);
    render(<AgentsDebuggerPanel client={fakeClient} />);
    await screen.findByText("plan");
    fireEvent.click(screen.getByText("act"));
    expect(await screen.findByText("act")).toBeInTheDocument();
  });

  it("selecting conversation messages highlights steps", async () => {
    (fakeClient.fetchAgentTraces as any).mockResolvedValue([{ id: "run-1", agent_name: "helper", started_at: new Date().toISOString() }]);
    (fakeClient.fetchAgentTraceById as any).mockResolvedValue(sampleDetail);
    render(<AgentsDebuggerPanel client={fakeClient} />);
    await screen.findByText("Plan step");
    fireEvent.click(screen.getByText("Plan step"));
    expect(await screen.findByText("plan")).toBeInTheDocument();
  });

  it("handles error state", async () => {
    (fakeClient.fetchAgentTraces as any).mockRejectedValueOnce(new Error("boom"));
    render(<AgentsDebuggerPanel client={fakeClient} />);
    expect(await screen.findByText("boom")).toBeInTheDocument();
  });
});
