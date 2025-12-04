import type { Diagnostic } from "../api/types";

export interface LineDiagnostics {
  line: number;
  diagnostics: Diagnostic[];
}

export function groupDiagnosticsByLine(diagnostics: Diagnostic[]): LineDiagnostics[] {
  const byLine = new Map<number, Diagnostic[]>();

  for (const diag of diagnostics) {
    const line = diag.range?.start?.line ?? 0;
    const existing = byLine.get(line);
    if (existing) {
      existing.push(diag);
    } else {
      byLine.set(line, [diag]);
    }
  }

  return Array.from(byLine.entries())
    .sort((a, b) => a[0] - b[0])
    .map(([line, diags]) => ({ line, diagnostics: diags }));
}

export function countDiagnosticsBySeverity(
  diagnostics: Diagnostic[]
): { error: number; warning: number; info: number } {
  let error = 0;
  let warning = 0;
  let info = 0;
  for (const diag of diagnostics) {
    if (diag.severity === "error") error += 1;
    else if (diag.severity === "warning") warning += 1;
    else info += 1;
  }
  return { error, warning, info };
}
