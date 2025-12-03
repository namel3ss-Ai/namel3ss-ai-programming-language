import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import OptimizerPanel from "../panels/OptimizerPanel";
import { ApiClient } from "../api/client";

const fakeClient = {
  ...ApiClient,
  fetchOptimizerSuggestions: vi.fn(),
  scanOptimizer: vi.fn(),
  applySuggestion: vi.fn(),
  rejectSuggestion: vi.fn(),
};

describe("OptimizerPanel", () => {
  beforeEach(() => {
    (fakeClient.fetchOptimizerSuggestions as any).mockResolvedValue({
      suggestions: [{ id: "s1", title: "Fix flow", kind: "flow-optimization", status: "pending", severity: "warning" }],
    });
    (fakeClient.scanOptimizer as any).mockResolvedValue({ created: ["s1"] });
    (fakeClient.applySuggestion as any).mockResolvedValue({ status: "applied" });
    (fakeClient.rejectSuggestion as any).mockResolvedValue({ status: "rejected" });
  });

  it("renders suggestions and can apply", async () => {
    render(<OptimizerPanel client={fakeClient} />);
    expect(await screen.findByText("Fix flow")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Apply"));
    await waitFor(() => expect(fakeClient.applySuggestion).toHaveBeenCalledWith("s1"));
  });

  it("shows empty state", async () => {
    (fakeClient.fetchOptimizerSuggestions as any).mockResolvedValueOnce({ suggestions: [] });
    render(<OptimizerPanel client={fakeClient} />);
    expect(await screen.findByText("No suggestions yet.")).toBeInTheDocument();
  });

  it("shows error state", async () => {
    (fakeClient.fetchOptimizerSuggestions as any).mockRejectedValueOnce(new Error("fail"));
    render(<OptimizerPanel client={fakeClient} />);
    expect(await screen.findByText("fail")).toBeInTheDocument();
  });
});
