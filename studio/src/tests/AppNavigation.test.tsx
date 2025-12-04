import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, fireEvent, screen } from "@testing-library/react";
import App from "../App";
import * as apiClient from "../api/client";

describe("App navigation", () => {
  it("includes IDE tab and shows IDE panel when selected", async () => {
    vi.spyOn(apiClient.ApiClient, "fetchPlugins").mockResolvedValue([] as any);
    vi.spyOn(apiClient.ApiClient, "fetchLastTrace").mockResolvedValue(null as any);

    render(<App />);

    const ideTab = screen.getByText("IDE");
    expect(ideTab).toBeInTheDocument();

    fireEvent.click(ideTab);

    expect(await screen.findByText("Run diagnostics")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Plugins" })).toBeInTheDocument();
  });
});
