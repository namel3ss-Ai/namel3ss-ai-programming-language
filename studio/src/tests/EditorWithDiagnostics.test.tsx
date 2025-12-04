import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, fireEvent, screen } from "@testing-library/react";
import { EditorWithDiagnostics } from "../editor/EditorWithDiagnostics";
import * as apiClient from "../api/client";

describe("EditorWithDiagnostics", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("runs diagnostics and displays results", async () => {
    const mock = vi.spyOn(apiClient, "postDiagnostics").mockResolvedValue({
      diagnostics: [
        {
          code: "N3-001",
          severity: "error",
          message: "Example error",
          range: { start: { line: 0, column: 0 }, end: { line: 0, column: 5 } },
        },
      ],
      summary: { errors: 1 },
      success: false,
    });

    render(<EditorWithDiagnostics initialSource={"app Demo"} />);
    fireEvent.click(screen.getByText("Run diagnostics"));
    expect(mock).toHaveBeenCalledWith("app Demo");
    expect(await screen.findByText("Example error")).toBeInTheDocument();
  });

  it("shows error message when diagnostics call fails", async () => {
    vi.spyOn(apiClient, "postDiagnostics").mockRejectedValueOnce(new Error("boom"));
    render(<EditorWithDiagnostics initialSource={"app Demo"} />);
    fireEvent.click(screen.getByText("Run diagnostics"));
    expect(await screen.findByText("Diagnostics failed")).toBeInTheDocument();
  });
});
