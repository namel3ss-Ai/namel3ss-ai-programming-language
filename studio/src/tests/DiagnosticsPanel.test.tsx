import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import DiagnosticsPanel from "../panels/DiagnosticsPanel";
import { ApiClient } from "../api/client";

const fakeClient = {
  ...ApiClient,
  fetchDiagnostics: vi.fn(),
};

describe("DiagnosticsPanel", () => {
  beforeEach(() => {
    (fakeClient.fetchDiagnostics as any).mockResolvedValue({
      summary: { error_count: 0, warning_count: 1, strict: false },
      diagnostics: [
        {
          code: "N3-LANG-001",
          severity: "warning",
          category: "lang-spec",
          message: "Page has no route",
          location: "page:home",
          hint: "Add route",
        },
      ],
    });
  });

  it("runs diagnostics and renders table", async () => {
    render(<DiagnosticsPanel code={'page "home":\n  title "Home"'} client={fakeClient} />);
    fireEvent.click(screen.getByText("Run diagnostics"));
    await waitFor(() => expect(fakeClient.fetchDiagnostics).toHaveBeenCalled());
    expect(await screen.findByText("Page has no route")).toBeInTheDocument();
  });
});
