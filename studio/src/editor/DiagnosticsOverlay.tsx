import React from "react";
import type { Diagnostic } from "../api/types";
import { countDiagnosticsBySeverity, groupDiagnosticsByLine } from "./diagnostics";

export interface DiagnosticsOverlayProps {
  diagnostics: Diagnostic[];
  activeLine?: number | null;
  className?: string;
}

export const DiagnosticsOverlay: React.FC<DiagnosticsOverlayProps> = ({
  diagnostics,
  activeLine,
  className,
}) => {
  const summary = countDiagnosticsBySeverity(diagnostics);
  const byLine = groupDiagnosticsByLine(diagnostics);

  return (
    <div className={className ?? "n3-diagnostics-overlay"}>
      <div className="n3-diagnostics-summary">
        <span>Errors: {summary.error}</span>
        <span>Warnings: {summary.warning}</span>
        <span>Info: {summary.info}</span>
      </div>
      <ul className="n3-diagnostics-list">
        {byLine.map(({ line, diagnostics: diags }) => (
          <li
            key={line}
            className={
              "n3-diagnostics-line" + (activeLine != null && activeLine === line ? " n3-active-line" : "")
            }
          >
            <span className="n3-diagnostics-line-number">Line {line + 1}</span>
            <ul className="n3-diagnostics-line-items">
              {diags.map((d, idx) => (
                <li key={d.code + "-" + idx.toString()} className={`n3-diagnostic-item n3-diagnostic-${d.severity}`}>
                  <span className="n3-diagnostic-code">{d.code}</span>{" "}
                  <span className="n3-diagnostic-message">{d.message}</span>
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
    </div>
  );
};
