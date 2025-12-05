import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { TraceDetailPanel } from "../components/TraceDetailPanel";
import * as apiClient from "../api/client";

describe("TraceDetailPanel", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders nothing when traceId is null", () => {
    const { container } = render(<TraceDetailPanel traceId={null} onClose={() => {}} />);
    expect(container.firstChild).toBeNull();
  });

  it("loads and displays trace detail", async () => {
    vi.spyOn(apiClient.ApiClient, "fetchTraceById").mockResolvedValue({
      id: "trace-1",
      status: "done",
      started_at: "2025-01-01T00:00:00Z",
      events: [
        {
          id: "step-1",
          kind: "step",
          status: "done",
          event: "condition.eval",
          condition: "x > 1",
          result: true,
        },
      ],
    } as any);

    render(<TraceDetailPanel traceId="trace-1" onClose={() => {}} />);

    expect(screen.getByText("Loading trace...")).toBeInTheDocument();

    const idText = await screen.findByText("ID: trace-1");
    expect(idText).toBeInTheDocument();
    expect(screen.getByText("step (done)")).toBeInTheDocument();
    expect(screen.getByText("Conditions")).toBeInTheDocument();
  });

  it("shows error message when loading fails", async () => {
    vi.spyOn(apiClient.ApiClient, "fetchTraceById").mockRejectedValue(new Error("boom"));

    render(<TraceDetailPanel traceId="trace-1" onClose={() => {}} />);

    const error = await screen.findByText("Failed to load trace");
    expect(error).toBeInTheDocument();
  });

  it("allows selecting steps and shows step detail", async () => {
    vi.spyOn(apiClient.ApiClient, "fetchTraceById").mockResolvedValue({
      id: "trace-1",
      status: "done",
      events: [
        { id: "step-1", kind: "first", status: "done" },
        { id: "step-2", kind: "second", status: "pending" },
      ],
    } as any);

    render(<TraceDetailPanel traceId="trace-1" onClose={() => {}} />);

    await screen.findByText("first (done)");

    fireEvent.click(screen.getByText("second (pending)"));

    expect(await screen.findByText("Kind: second")).toBeInTheDocument();
  });
});
