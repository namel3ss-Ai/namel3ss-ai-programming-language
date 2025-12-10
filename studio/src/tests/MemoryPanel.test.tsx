import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { vi } from "vitest";
import MemoryPanel from "../panels/MemoryPanel";
import { ApiClient } from "../api/client";

const setupClient = () => {
  const client = {
    ...ApiClient,
    fetchStudioSummary: vi.fn().mockResolvedValue({
      summary: { ai_calls: ["support_bot"] },
    }),
    fetchMemoryPlan: vi.fn().mockResolvedValue({
      ai: "support_bot",
      kinds: [
        {
          kind: "short_term",
          enabled: true,
          scope: "per_session",
          retention_days: 7,
          pii_policy: "none",
          window: 5,
          pipeline: [
            { name: "summarise_short", type: "llm_summariser", target_kind: "episodic", max_tokens: 256, embedding_model: null },
          ],
        },
        {
          kind: "long_term",
          enabled: true,
          scope: "per_user",
          retention_days: 365,
          pii_policy: "strip-email-ip",
          store: "chat_long",
          time_decay: { half_life_days: 30 },
          pipeline: [],
        },
      ],
      recall: [{ source: "short_term", count: 5 }],
    }),
    fetchMemorySessions: vi.fn().mockResolvedValue({
      ai: "support_bot",
      sessions: [
        { id: "sess_a", turns: 2, last_activity: "2025-12-05T10:12:34Z", user_id: "user-123" },
        { id: "sess_b", turns: 1, last_activity: null, user_id: null },
      ],
    }),
    fetchMemoryState: vi.fn().mockResolvedValue({
      ai: "support_bot",
      session_id: "sess_a",
      user_id: "user-123",
      kinds: {
        short_term: { window: 5, turns: [{ role: "user", content: "Hello" }] },
        long_term: { store: "chat_long", items: [{ id: "lt1", summary: "summary", created_at: null }] },
      },
      policies: {
        short_term: {
          scope: "per_session",
          requested_scope: "per_session",
          scope_fallback: false,
          retention_days: 7,
          pii_policy: "none",
        },
        long_term: {
          scope: "per_user",
          requested_scope: "per_user",
          scope_fallback: false,
          retention_days: 365,
          pii_policy: "strip-email-ip",
          time_decay: { half_life_days: 30 },
        },
      },
      recall_snapshot: {
        timestamp: "2025-12-05T10:12:34Z",
        rules: [{ source: "short_term", count: 5 }],
        messages: [{ role: "user", content: "Hello" }],
        diagnostics: [{ kind: "short_term", selected: 2 }],
      },
    }),
  };
  return client;
};

describe("MemoryPanel", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders plan and state for selected AI", async () => {
    const client = setupClient();
    render(<MemoryPanel client={client} />);
    await waitFor(() => expect(client.fetchStudioSummary).toHaveBeenCalled());
    await waitFor(() => expect(client.fetchMemoryPlan).toHaveBeenCalledWith("support_bot"));
    await waitFor(() => expect(client.fetchMemorySessions).toHaveBeenCalledWith("support_bot"));
    await waitFor(() => expect(client.fetchMemoryState).toHaveBeenCalledWith("support_bot", expect.objectContaining({ sessionId: "sess_a" })));

    expect(await screen.findByText(/Short-Term — Enabled/i)).toBeInTheDocument();
    expect(screen.getByText(/Pipeline/i)).toBeInTheDocument();
    const scopes = await screen.findAllByText(/Scope: per_session/i);
    expect(scopes.length).toBeGreaterThan(0);
    expect(screen.getByText(/User ID: user-123/i)).toBeInTheDocument();
    expect(screen.getByText("Hello")).toBeInTheDocument();
    expect(screen.getByText(/selected 2/i)).toBeInTheDocument();
  });

  it("inspects memory for a typed user id", async () => {
    const client = setupClient();
    client.fetchMemoryState = vi
      .fn()
      .mockResolvedValueOnce({
        ai: "support_bot",
        session_id: "sess_a",
        user_id: "user-123",
        kinds: { short_term: { window: 5, turns: [{ role: "user", content: "Hello" }] } },
        policies: { short_term: { scope: "per_session", requested_scope: "per_session", pii_policy: "none" } },
      })
      .mockResolvedValueOnce({
        ai: "support_bot",
        session_id: null,
        user_id: "user-999",
        kinds: {
          long_term: { store: "chat_long", items: [{ id: "lt2", summary: "user summary", created_at: null }] },
        },
        policies: {
          long_term: { scope: "per_user", requested_scope: "per_user", pii_policy: "strip-email-ip" },
        },
      });

    render(<MemoryPanel client={client} />);
    await waitFor(() => expect(client.fetchMemoryState).toHaveBeenCalledWith("support_bot", expect.objectContaining({ sessionId: "sess_a" })));

    const input = await screen.findByPlaceholderText("user-123");
    fireEvent.change(input, { target: { value: "user-999" } });
    fireEvent.click(screen.getByText("Inspect User"));

    await waitFor(() => expect(client.fetchMemoryState).toHaveBeenCalledWith("support_bot", expect.objectContaining({ userId: "user-999" })));
    expect(await screen.findByText(/User ID: user-999/i)).toBeInTheDocument();
    expect(screen.getByText(/user summary/i)).toBeInTheDocument();
  });
});
