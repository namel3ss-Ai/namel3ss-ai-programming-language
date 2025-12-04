import React from "react";
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { DiagnosticsOverlay } from "../editor/DiagnosticsOverlay";
import type { Diagnostic } from "../api/types";

const sampleDiagnostics: Diagnostic[] = [
  {
    code: "N3-1",
    severity: "error",
    message: "First error",
    range: { start: { line: 0, column: 0 }, end: { line: 0, column: 1 } },
  },
  {
    code: "N3-2",
    severity: "error",
    message: "Second error",
    range: { start: { line: 1, column: 0 }, end: { line: 1, column: 1 } },
  },
  {
    code: "N3-3",
    severity: "warning",
    message: "Warn",
    range: { start: { line: 1, column: 2 }, end: { line: 1, column: 3 } },
  },
  {
    code: "N3-4",
    severity: "info",
    message: "Info",
    range: { start: { line: 2, column: 0 }, end: { line: 2, column: 1 } },
  },
];

describe("DiagnosticsOverlay", () => {
  it("renders summary counts correctly", () => {
    const { container } = render(<DiagnosticsOverlay diagnostics={sampleDiagnostics} />);
    const summary = container.querySelector(".n3-diagnostics-summary");
    expect(summary?.textContent).toContain("Errors: 2");
    expect(summary?.textContent).toContain("Warnings: 1");
    expect(summary?.textContent).toContain("Info: 1");
  });

  it("renders grouped diagnostics by line", () => {
    const { container } = render(<DiagnosticsOverlay diagnostics={sampleDiagnostics} />);
    const lines = container.querySelectorAll(".n3-diagnostics-line");
    expect(lines.length).toBe(3);
  });
});
