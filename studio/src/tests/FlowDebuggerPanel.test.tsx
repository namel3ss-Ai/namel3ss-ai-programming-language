import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import TracePanel from "../panels/TracePanel";
import * as apiClient from "../api/client";

describe("TracePanel with condition traces", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("shows conditions count via detail panel rendering", async () => {
    vi.spyOn(apiClient.ApiClient, "fetchTrace").mockResolvedValue({
      trace: {
        id: "t1",
        events: [
          { id: "c1", event: "condition.eval", condition: "x > 1", result: true, scope: "flow" },
          { id: "g1", event: "flow.goto", from_flow: "a", to_flow: "b" },
        ],
      },
    } as any);

    render(<TracePanel client={apiClient.ApiClient} />);

    fireEvent.click(screen.getByText("Refresh"));

    const json = await screen.findByText(/condition.eval/);
    expect(json).toBeInTheDocument();
  });
});
