import { describe, it, expect } from "vitest";
import { countDiagnosticsBySeverity, groupDiagnosticsByLine } from "../editor/diagnostics";
import type { Diagnostic } from "../api/types";

describe("groupDiagnosticsByLine", () => {
  it("groups diagnostics by line sorted ascending", () => {
    const diagnostics: Diagnostic[] = [
      {
        code: "D1",
        severity: "error",
        message: "First",
        range: { start: { line: 2, column: 0 }, end: { line: 2, column: 5 } },
      },
      {
        code: "D2",
        severity: "warning",
        message: "Second",
        range: { start: { line: 0, column: 1 }, end: { line: 0, column: 3 } },
      },
      {
        code: "D3",
        severity: "info",
        message: "Third",
        range: { start: { line: 2, column: 10 }, end: { line: 2, column: 12 } },
      },
    ];

    const grouped = groupDiagnosticsByLine(diagnostics);
    expect(grouped.length).toBe(2);
    expect(grouped[0].line).toBe(0);
    expect(grouped[1].line).toBe(2);
    expect(grouped[1].diagnostics.map((d) => d.code)).toEqual(["D1", "D3"]);
  });
});

describe("countDiagnosticsBySeverity", () => {
  it("counts diagnostics by severity", () => {
    const diagnostics: Diagnostic[] = [
      { code: "E1", severity: "error", message: "err" },
      { code: "E2", severity: "error", message: "err2" },
      { code: "W1", severity: "warning", message: "warn" },
      { code: "I1", severity: "info", message: "info" },
    ];

    const counts = countDiagnosticsBySeverity(diagnostics);
    expect(counts.error).toBe(2);
    expect(counts.warning).toBe(1);
    expect(counts.info).toBe(1);
  });
});
