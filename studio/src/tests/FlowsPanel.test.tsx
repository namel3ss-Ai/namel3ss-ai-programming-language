import React from "react";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { vi } from "vitest";
import FlowsPanel from "../panels/FlowsPanel";
import { ApiClient } from "../api/client";

const fakeClient = {
  ...ApiClient,
  fetchFlows: vi.fn(),
  fetchTriggers: vi.fn(),
  fireTrigger: vi.fn(),
  fetchTraces: vi.fn(),
  fetchTraceById: vi.fn(),
};

describe("FlowsPanel", () => {
  beforeEach(() => {
    (fakeClient.fetchFlows as any).mockResolvedValue({
      flows: [{ name: "pipeline", description: "demo", steps: 2 }],
    });
    (fakeClient.fetchTriggers as any).mockResolvedValue({
      triggers: [{ id: "t1", kind: "http", flow_name: "pipeline", enabled: true, config: {}, last_fired: null }],
    });
    (fakeClient.fireTrigger as any).mockResolvedValue({ job_id: "job-1" });
    (fakeClient.fetchTraces as any).mockResolvedValue([
      { id: "trace-1", started_at: new Date().toISOString(), status: "completed", duration_seconds: 1.2 },
    ]);
    (fakeClient.fetchTraceById as any).mockResolvedValue({
      id: "trace-1",
      started_at: new Date().toISOString(),
      status: "completed",
      duration_seconds: 1.2,
      graph: { nodes: [{ id: "n1", label: "step1", kind: "ai" }], edges: [] },
      events: [{ id: "e1", node_id: "n1", kind: "log", message: "ok" }],
      trace: {},
    });
  });

  it("loads traces, flows, triggers and can fire", async () => {
    render(<FlowsPanel code={'flow "pipeline":\n'} client={fakeClient} />);
    await waitFor(() => expect(fakeClient.fetchTraces).toHaveBeenCalled());
    fireEvent.click(screen.getByText("Refresh"));
    await waitFor(() => expect(fakeClient.fetchFlows).toHaveBeenCalled());
    const tables = await screen.findAllByRole("table");
    const flowTable = tables[0];
    const flowCell = within(flowTable).getByRole("cell", { name: "pipeline" });
    expect(flowCell).toBeInTheDocument();
    const triggerTable = tables[1];
    const fireButton = within(triggerTable).getByRole("button", { name: "Fire" });
    fireEvent.click(fireButton);
    await waitFor(() => expect(fakeClient.fireTrigger).toHaveBeenCalledWith("t1", {}));
  });

  it("shows empty states", async () => {
    (fakeClient.fetchFlows as any).mockResolvedValueOnce({ flows: [] });
    (fakeClient.fetchTriggers as any).mockResolvedValueOnce({ triggers: [] });
    (fakeClient.fetchTraces as any).mockResolvedValueOnce([]);
    render(<FlowsPanel code={'flow "pipeline":\n'} client={fakeClient} />);
    await screen.findByText("No traces yet.");
    fireEvent.click(screen.getByText("Refresh"));
    expect(await screen.findByText("No flows detected.")).toBeInTheDocument();
    expect(await screen.findByText("No triggers registered.")).toBeInTheDocument();
  });

  it("shows error state", async () => {
    (fakeClient.fetchFlows as any).mockRejectedValueOnce(new Error("fetch failed"));
    render(<FlowsPanel code={'flow "pipeline":\n'} client={fakeClient} />);
    fireEvent.click(screen.getByText("Refresh"));
    expect(await screen.findByText("fetch failed")).toBeInTheDocument();
  });
});
