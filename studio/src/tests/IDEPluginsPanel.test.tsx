import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { IDEPluginsPanel } from "../panels/IDEPluginsPanel";
import * as apiClient from "../api/client";

describe("IDEPluginsPanel", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("loads and displays plugins", async () => {
    vi.spyOn(apiClient.ApiClient, "fetchPlugins").mockResolvedValue([
      {
        id: "example",
        name: "Example Plugin",
        version: "1.0.0",
        description: "Example",
        entrypoints: {},
        tags: ["tools"],
      },
    ] as any);

    render(<IDEPluginsPanel />);

    expect(screen.getByText("Loading plugins...")).toBeInTheDocument();

    const name = await screen.findByText("Example Plugin");
    expect(name).toBeInTheDocument();
  });

  it("shows error message when fetch fails", async () => {
    vi.spyOn(apiClient.ApiClient, "fetchPlugins").mockRejectedValue(new Error("boom"));

    render(<IDEPluginsPanel />);

    const error = await screen.findByText("Failed to load plugins");
    expect(error).toBeInTheDocument();
  });
});
