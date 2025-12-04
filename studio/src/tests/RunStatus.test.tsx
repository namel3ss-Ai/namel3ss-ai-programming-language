import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { RunStatus } from "../components/RunStatus";

describe("RunStatus", () => {
  it("shows running state when isRunning is true", () => {
    render(<RunStatus isRunning={true} />);
    expect(screen.getByText("Running app...")).toBeInTheDocument();
  });

  it("shows idle message when no runs yet", () => {
    render(<RunStatus isRunning={false} />);
    expect(screen.getByText("App has not been run yet.")).toBeInTheDocument();
  });

  it("shows OK message when lastStatus is ok", () => {
    render(<RunStatus isRunning={false} lastStatus="ok" lastMessage="All good" />);
    expect(screen.getByText("Last run: OK")).toBeInTheDocument();
    expect(screen.getByText("All good")).toBeInTheDocument();
  });

  it("shows error message when lastStatus is error", () => {
    render(<RunStatus isRunning={false} lastStatus="error" lastError="boom" />);
    expect(screen.getByText("Last run: Error")).toBeInTheDocument();
    expect(screen.getByText("boom")).toBeInTheDocument();
  });
});
