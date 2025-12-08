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
      pages: [
        { name: "home", route: "/", title: "Home" },
        { name: "chat", route: "/chat", title: "Chat" },
      ],
    });
    (fakeClient.fetchPageUI as any).mockResolvedValue({
      ui: {
        pages: [
          {
                name: "home",
                route: "/",
                layout: [
                    {
                      type: "section",
                      name: "main",
                      layout: [
                        {
                          type: "button",
                          label: "Go to Chat",
                          className: "primary-btn",
                          style: { background: "#000" },
                          onClick: { kind: "navigate", target: { pageName: "chat", path: "/chat" } },
                        },
                      ],
                    },
                  ],
          },
          {
            name: "chat",
            route: "/chat",
            layout: [
              {
                type: "section",
                name: "main",
                layout: [{ type: "text", text: "Chat" }],
              },
            ],
          },
        ],
      },
    });
  });

  it("loads and displays pages", async () => {
    render(<PagesPanel code={'page "home":\n  route "/"\n'} client={fakeClient} />);
    fireEvent.click(screen.getByText("Refresh"));
    await waitFor(() => expect(fakeClient.fetchPages).toHaveBeenCalled());
    expect(await screen.findByText("home")).toBeInTheDocument();
  });

  it("navigates between pages in preview when clicking navigate button", async () => {
    render(<PagesPanel code={'page "home":\n  route "/"\n'} client={fakeClient} />);
    fireEvent.click(screen.getByText("Refresh"));
    await waitFor(() => expect(fakeClient.fetchPages).toHaveBeenCalled());
    fireEvent.click(await screen.findByText("home"));
    await waitFor(() => expect(fakeClient.fetchPageUI).toHaveBeenCalled());
    const btn = await screen.findByText("Go to Chat");
    fireEvent.click(btn);
    await waitFor(() => expect(fakeClient.fetchPageUI).toHaveBeenCalledTimes(2));
    expect(await screen.findByText(/Current page: chat/)).toBeInTheDocument();
  });

  it("applies className and style to preview buttons", async () => {
    render(<PagesPanel code={'page "home":\n  route "/"\n'} client={fakeClient} />);
    fireEvent.click(screen.getByText("Refresh"));
    await waitFor(() => expect(fakeClient.fetchPages).toHaveBeenCalled());
    fireEvent.click(await screen.findByText("home"));
    await waitFor(() => expect(fakeClient.fetchPageUI).toHaveBeenCalled());
    const btn = await screen.findByText("Go to Chat");
    expect(btn.className).toContain("primary-btn");
    expect(btn.getAttribute("style") || "").toContain("background");
  });
});
