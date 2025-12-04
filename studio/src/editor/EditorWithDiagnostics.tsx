import React, { useCallback, useState } from "react";
import { CodeEditor } from "./CodeEditor";
import { DiagnosticsOverlay } from "./DiagnosticsOverlay";
import { postDiagnostics } from "../api/client";
import type { Diagnostic } from "../api/types";

export interface EditorWithDiagnosticsProps {
  initialSource?: string;
  className?: string;
}

export const EditorWithDiagnostics: React.FC<EditorWithDiagnosticsProps> = ({ initialSource, className }) => {
  const [source, setSource] = useState(initialSource ?? "");
  const [diagnostics, setDiagnostics] = useState<Diagnostic[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSourceChange = useCallback((value: string) => {
    setSource(value);
    setErrorMessage(null);
  }, []);

  const handleRunDiagnostics = useCallback(async () => {
    setIsRunning(true);
    setErrorMessage(null);
    try {
      const res = await postDiagnostics(source);
      setDiagnostics(res.diagnostics ?? []);
    } catch (err: any) {
      setErrorMessage("Diagnostics failed");
    } finally {
      setIsRunning(false);
    }
  }, [source]);

  return (
    <div className={className ?? "n3-editor-with-diagnostics"}>
      <div className="n3-editor-toolbar">
        <button type="button" onClick={handleRunDiagnostics} disabled={isRunning}>
          {isRunning ? "Running diagnostics..." : "Run diagnostics"}
        </button>
        {errorMessage && <span className="n3-editor-error">{errorMessage}</span>}
      </div>
      <div className="n3-editor-main">
        <CodeEditor value={source} onChange={handleSourceChange} />
      </div>
      <DiagnosticsOverlay diagnostics={diagnostics} />
    </div>
  );
};
