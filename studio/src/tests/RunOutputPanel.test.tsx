import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, fireEvent, screen } from "@testing-library/react";
import { RunOutputPanel } from "../components/RunOutputPanel";

const trace = {
  id: "trace-1",
  status: "done",
  kind: "app_run",
  started_at: "2024-01-01T00:00:00Z",
} as any;

describe("RunOutputPanel", () => {
  it("shows empty messages when no run or trace yet", () => {
    render(
      <RunOutputPanel lastRun={null} lastTrace={null} onRefresh={() => {}} isRefreshing={false} />
    );
    expect(screen.getByText("No runs yet.")).toBeInTheDocument();
    expect(screen.getByText("No last trace available.")).toBeInTheDocument();
  });

  it("renders last run response details", () => {
    render(
      <RunOutputPanel
        lastRun={{ status: "ok", message: "Done", error: null }}
        lastTrace={null}
        onRefresh={() => {}}
        isRefreshing={false}
      />
    );
    expect(screen.getByText("Status: ok")).toBeInTheDocument();
    expect(screen.getByText("Message: Done")).toBeInTheDocument();
  });

  it("renders last trace details", () => {
    render(
      <RunOutputPanel
        lastRun={null}
        lastTrace={trace}
        onRefresh={() => {}}
        isRefreshing={false}
      />
    );
    expect(screen.getByText("ID: trace-1")).toBeInTheDocument();
    expect(screen.getByText("Status: done")).toBeInTheDocument();
  });

  it("calls onRefresh when Refresh is clicked", () => {
    const onRefresh = vi.fn();
    render(
      <RunOutputPanel lastRun={null} lastTrace={null} onRefresh={onRefresh} isRefreshing={false} />
    );
    fireEvent.click(screen.getByText("Refresh"));
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });

  it("calls onViewTrace when 'View full trace' is clicked", () => {
    const onRefresh = vi.fn();
    const onViewTrace = vi.fn();
    render(
      <RunOutputPanel
        lastRun={null}
        lastTrace={trace}
        onRefresh={onRefresh}
        isRefreshing={false}
        onViewTrace={onViewTrace}
      />
    );

    fireEvent.click(screen.getByText("View full trace"));
    expect(onViewTrace).toHaveBeenCalledTimes(1);
    expect(onViewTrace).toHaveBeenCalledWith("trace-1");
  });
});
