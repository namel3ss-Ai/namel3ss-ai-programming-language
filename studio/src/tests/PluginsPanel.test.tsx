import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import PluginsPanel from "../panels/PluginsPanel";
import { ApiClient } from "../api/client";

const fakeClient = {
  ...ApiClient,
  fetchPlugins: vi.fn(),
  loadPlugin: vi.fn(),
  unloadPlugin: vi.fn(),
};

describe("PluginsPanel", () => {
  beforeEach(() => {
    (fakeClient.fetchPlugins as any).mockResolvedValue([
      { id: "p1", name: "PluginOne", version: "0.1.0", compatible: true, loaded: false, enabled: true },
    ]);
    (fakeClient.loadPlugin as any).mockResolvedValue({ plugin: { id: "p1" } });
    (fakeClient.unloadPlugin as any).mockResolvedValue({ status: "ok" });
  });

  it("lists plugins and can load", async () => {
    render(<PluginsPanel client={fakeClient} />);
    fireEvent.click(screen.getByText("Refresh"));
    await waitFor(() => expect(fakeClient.fetchPlugins).toHaveBeenCalled());
    expect(await screen.findByText("PluginOne")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Load"));
    await waitFor(() => expect(fakeClient.loadPlugin).toHaveBeenCalledWith("p1"));
  });

  it("shows empty state", async () => {
    (fakeClient.fetchPlugins as any).mockResolvedValueOnce([]);
    render(<PluginsPanel client={fakeClient} />);
    fireEvent.click(screen.getByText("Refresh"));
    expect(await screen.findByText("No plugins found.")).toBeInTheDocument();
  });

  it("shows error state", async () => {
    (fakeClient.fetchPlugins as any).mockRejectedValueOnce(new Error("boom"));
    render(<PluginsPanel client={fakeClient} />);
    fireEvent.click(screen.getByText("Refresh"));
    expect(await screen.findByText("boom")).toBeInTheDocument();
  });
});
