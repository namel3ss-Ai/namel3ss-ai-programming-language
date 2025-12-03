import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import PagesPanel from "../panels/PagesPanel";
import { ApiClient } from "../api/client";

const fakeClient = {
  ...ApiClient,
  fetchPages: vi.fn(),
  fetchPageUI: vi.fn(),
};

describe("PagesPanel", () => {
  beforeEach(() => {
    (fakeClient.fetchPages as any).mockResolvedValue({
      pages: [{ name: "home", route: "/", title: "Home" }],
    });
    (fakeClient.fetchPageUI as any).mockResolvedValue({
      ui: { name: "home", route: "/", sections: [] },
    });
  });

  it("loads and displays pages", async () => {
    render(<PagesPanel code={'page "home":\n  route "/"\n'} client={fakeClient} />);
    fireEvent.click(screen.getByText("Refresh"));
    await waitFor(() => expect(fakeClient.fetchPages).toHaveBeenCalled());
    expect(await screen.findByText("home")).toBeInTheDocument();
  });
});
