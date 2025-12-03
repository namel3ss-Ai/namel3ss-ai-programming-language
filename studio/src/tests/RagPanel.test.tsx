import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import RagMemoryPanel from "../panels/RagMemoryPanel";
import { ApiClient } from "../api/client";

const fakeClient = {
  ...ApiClient,
  fetchStudioSummary: vi.fn(),
  queryRag: vi.fn(),
};

describe("RAG panel", () => {
  beforeEach(() => {
    (fakeClient.fetchStudioSummary as any).mockResolvedValue({
      summary: {
        memory_items: 1,
        rag_documents: 2,
        total_agents: 1,
        total_flows: 1,
      },
    });
    (fakeClient.queryRag as any).mockResolvedValue({
      results: [{ text: "result text", score: 0.9, source: "default" }],
    });
  });

  it("renders summary and handles query", async () => {
    render(<RagMemoryPanel client={fakeClient} />);
    await waitFor(() => expect(fakeClient.fetchStudioSummary).toHaveBeenCalled());
    fireEvent.change(screen.getByPlaceholderText("Search text"), {
      target: { value: "hello" },
    });
    fireEvent.click(screen.getByText("Search"));
    await waitFor(() => expect(fakeClient.queryRag).toHaveBeenCalled());
    expect(await screen.findByText("result text")).toBeInTheDocument();
  });
});
