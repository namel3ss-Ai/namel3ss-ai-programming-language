import React, { useCallback, useEffect, useState } from "react";
import { CodeEditor } from "./CodeEditor";
import { DiagnosticsOverlay } from "./DiagnosticsOverlay";
import { postDiagnostics, postFmtPreview } from "../api/client";
import type { Diagnostic } from "../api/types";
import { CommandPalette, CommandPaletteItem } from "../components/CommandPalette";
import { TemplateWizard } from "../components/TemplateWizard";
import type { Template } from "../templates/templates";

export interface EditorWithDiagnosticsProps {
  initialSource?: string;
  className?: string;
  onSourceChange?: (newSource: string) => void;
  externalDiagnosticsRequestId?: number;
}

export const EditorWithDiagnostics: React.FC<EditorWithDiagnosticsProps> = ({
  initialSource,
  className,
  onSourceChange,
  externalDiagnosticsRequestId,
}) => {
  const [source, setSource] = useState(initialSource ?? "");
  const [diagnostics, setDiagnostics] = useState<Diagnostic[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isFormatting, setIsFormatting] = useState(false);
  const [formatMessage, setFormatMessage] = useState<string | null>(null);
  const [isPaletteOpen, setIsPaletteOpen] = useState(false);
  const [isTemplateWizardOpen, setIsTemplateWizardOpen] = useState(false);
  const [lastDiagnosticsRequestId, setLastDiagnosticsRequestId] = useState<number>(0);

  const handleSourceChange = useCallback(
    (value: string) => {
      setSource(value);
      setErrorMessage(null);
      setFormatMessage(null);
      if (onSourceChange) {
        onSourceChange(value);
      }
    },
    [onSourceChange]
  );

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

  const handleFormat = useCallback(async () => {
    if (!source.trim()) {
      setFormatMessage(null);
      return;
    }
    setIsFormatting(true);
    setFormatMessage(null);
    try {
      const res = await postFmtPreview(source);
      if (res.changes_made && res.formatted !== source) {
        setSource(res.formatted);
        if (onSourceChange) {
          onSourceChange(res.formatted);
        }
        setFormatMessage("Formatted");
      } else {
        setFormatMessage("Already formatted");
      }
    } catch (err) {
      setFormatMessage("Formatting failed");
    } finally {
      setIsFormatting(false);
    }
  }, [onSourceChange, source]);

  const handleApplyTemplate = useCallback(
    (template: Template) => {
      setSource(template.content);
      setDiagnostics([]);
      setErrorMessage(null);
      setFormatMessage(null);
      if (onSourceChange) {
        onSourceChange(template.content);
      }
    },
    [onSourceChange]
  );

  const commands: CommandPaletteItem[] = [
    {
      id: "run-diagnostics",
      title: "Run diagnostics",
      description: "Analyze the current .ai source",
    },
    {
      id: "format-file",
      title: "Format file",
      description: "Run n3 fmt preview on the current buffer",
    },
  ];

  const handleRunCommand = useCallback(
    async (id: string) => {
      if (id === "run-diagnostics") {
        await handleRunDiagnostics();
      } else if (id === "format-file") {
        await handleFormat();
      }
      setIsPaletteOpen(false);
    },
    [handleRunDiagnostics, handleFormat]
  );

  const handleKeyDown = useCallback(
    async (e: React.KeyboardEvent<HTMLDivElement>) => {
      const isMac = navigator.platform.toLowerCase().includes("mac");
      const isMod = isMac ? e.metaKey : e.ctrlKey;

      if (isMod && e.key.toLowerCase() === "s") {
        e.preventDefault();
        if (!isFormatting) {
          await handleFormat();
        }
        return;
      }

      if (isMod && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setIsPaletteOpen(true);
      }
    },
    [handleFormat, isFormatting]
  );

  useEffect(() => {
    if (
      typeof externalDiagnosticsRequestId === "number" &&
      externalDiagnosticsRequestId > lastDiagnosticsRequestId
    ) {
      handleRunDiagnostics();
      setLastDiagnosticsRequestId(externalDiagnosticsRequestId);
    }
  }, [externalDiagnosticsRequestId, lastDiagnosticsRequestId, handleRunDiagnostics]);

  return (
    <div className={className ?? "n3-editor-with-diagnostics"} onKeyDown={handleKeyDown}>
      <div className="n3-editor-toolbar">
        <button type="button" onClick={handleRunDiagnostics} disabled={isRunning}>
          {isRunning ? "Running diagnostics..." : "Run diagnostics"}
        </button>
        <button type="button" onClick={handleFormat} disabled={isFormatting}>
          {isFormatting ? "Formatting..." : "Format"}
        </button>
        <button type="button" onClick={() => setIsTemplateWizardOpen(true)}>
          Templates
        </button>
        {errorMessage && <span className="n3-editor-error">{errorMessage}</span>}
        {formatMessage && <span className="n3-editor-format-message">{formatMessage}</span>}
      </div>
      <div className="n3-editor-main">
        <CodeEditor value={source} onChange={handleSourceChange} />
      </div>
      <DiagnosticsOverlay diagnostics={diagnostics} />
      <CommandPalette
        isOpen={isPaletteOpen}
        onClose={() => setIsPaletteOpen(false)}
        commands={commands}
        onRunCommand={handleRunCommand}
      />
      <TemplateWizard
        isOpen={isTemplateWizardOpen}
        onClose={() => setIsTemplateWizardOpen(false)}
        onApplyTemplate={handleApplyTemplate}
      />
    </div>
  );
};
