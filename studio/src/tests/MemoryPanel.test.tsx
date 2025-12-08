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
    fetchMemorySessions: vi.fn().mockResolvedValue({
      ai: "support_bot",
      sessions: [
        { id: "sess_a", turns: 2, last_activity: "2025-12-05T10:12:34Z", user_id: "user-123" },
        { id: "sess_b", turns: 1, last_activity: null, user_id: null },
      ],
    }),
    fetchMemorySessionDetail: vi.fn().mockResolvedValue({
      ai: "support_bot",
      session: "sess_a",
      user_id: "user-123",
      short_term: { window: 5, turns: [{ role: "user", content: "Hello" }] },
      long_term: { store: "chat_long", items: [{ id: "lt1", summary: "summary", created_at: null }] },
      profile: { store: "user_profile", facts: ["User likes football."] },
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
        },
        profile: {
          scope: "per_user",
          requested_scope: "per_user",
          scope_fallback: false,
          retention_days: 365,
          pii_policy: "strip-email-ip",
        },
      },
      last_recall_snapshot: {
        timestamp: "2025-12-05T10:12:34Z",
        rules: [{ source: "short_term", count: 5 }],
        messages: [{ role: "user", content: "Hello" }],
      },
    }),
    clearMemorySession: vi.fn().mockResolvedValue({ success: true }),
  };
  return client;
};

describe("MemoryPanel", () => {
  beforeEach(() => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders sessions and detail for selected AI", async () => {
    const client = setupClient();
    render(<MemoryPanel client={client} />);
    await waitFor(() => expect(client.fetchStudioSummary).toHaveBeenCalled());
    await waitFor(() => expect(client.fetchMemorySessions).toHaveBeenCalledWith("support_bot"));
    expect(await screen.findByText("sess_a")).toBeInTheDocument();
    expect(await screen.findByText("Conversation")).toBeInTheDocument();
    expect(screen.getByText("Hello")).toBeInTheDocument();
    expect(screen.getByText(/Scope: per_session/i)).toBeInTheDocument();
    expect(screen.getByText(/User ID: user-123/i)).toBeInTheDocument();
  });

  it("clears memory when requested", async () => {
    const client = setupClient();
    render(<MemoryPanel client={client} />);
    await waitFor(() => expect(client.fetchMemorySessionDetail).toHaveBeenCalled());
    fireEvent.click(await screen.findByText("Clear All"));
    await waitFor(() => expect(client.clearMemorySession).toHaveBeenCalledWith("support_bot", "sess_a", undefined));
  });
});
