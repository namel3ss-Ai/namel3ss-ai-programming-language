import React, { useCallback, useEffect, useMemo, useState } from "react";
import { EditorWithDiagnostics } from "../editor/EditorWithDiagnostics";
import { IDEPluginsPanel } from "./IDEPluginsPanel";
import { FileExplorer } from "../components/FileExplorer";
import { TabBar } from "../components/TabBar";
import { RunStatus } from "../components/RunStatus";
import { RunOutputPanel } from "../components/RunOutputPanel";
import { TraceDetailPanel } from "../components/TraceDetailPanel";
import { CommandPalette, CommandPaletteItem } from "../components/CommandPalette";
import { fetchExampleSource } from "../api/examples";
import {
  createInitialWorkspace,
  setActiveFile,
  createFile,
  updateFileContent,
  deleteFile,
  type WorkspaceState,
  markFileClean,
} from "../ide/workspace";
import { createInitialRunState, applyRunResponse, applyLastTrace, type IDERunState } from "../ide/runState";
import { ApiClient, postRunApp } from "../api/client";

export interface IDEPanelProps {
  initialExampleName?: string | null;
  initialTraceId?: string | null;
  exampleLoader?: (name: string) => Promise<{ name: string; path: string; source: string }>;
}

export const IDEPanel: React.FC<IDEPanelProps> = ({
  initialExampleName = null,
  initialTraceId = null,
  exampleLoader,
}) => {
  const [workspace, setWorkspace] = useState<WorkspaceState>(() => createInitialWorkspace());
  const [runState, setRunState] = useState<IDERunState>(() => createInitialRunState());
  const [isRunningApp, setIsRunningApp] = useState(false);
  const [isRefreshingRunInfo, setIsRefreshingRunInfo] = useState(false);
  const [lastRunStatus, setLastRunStatus] = useState<string | null>(null);
  const [lastRunMessage, setLastRunMessage] = useState<string | null>(null);
  const [lastRunError, setLastRunError] = useState<string | null>(null);
  const [isTraceDetailOpen, setIsTraceDetailOpen] = useState(false);
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);
  const [isIDEPaletteOpen, setIsIDEPaletteOpen] = useState(false);
  const [diagnosticsRequestId, setDiagnosticsRequestId] = useState(0);
  const [loadedExampleName, setLoadedExampleName] = useState<string | null>(null);
  const [exampleError, setExampleError] = useState<string | null>(null);

  const activeFile = useMemo(() => {
    if (!workspace.activeFileId) return null;
    return workspace.files.find((f) => f.id === workspace.activeFileId) ?? null;
  }, [workspace]);

  const ideCommands: CommandPaletteItem[] = useMemo(
    () => [
      {
        id: "ide.saveAndRun",
        title: "Save & Run current file",
        description: "Save buffer and run app",
      },
      {
        id: "ide.openLastTrace",
        title: "Open last trace",
        description: "Open trace detail for last run",
      },
      {
        id: "ide.runDiagnostics",
        title: "Run diagnostics on current file",
        description: "Analyze current buffer for issues",
      },
    ],
    []
  );

  const handleOpenFile = useCallback((fileId: string) => {
    setWorkspace((prev) => setActiveFile(prev, fileId));
  }, []);

  const handleCreateFile = useCallback(() => {
    setWorkspace((prev) => createFile(prev));
  }, []);

  const handleDeleteFile = useCallback((fileId: string) => {
    setWorkspace((prev) => deleteFile(prev, fileId));
  }, []);

  const handleSourceChange = useCallback(
    (newSource: string) => {
      if (!workspace.activeFileId) return;
      const currentId = workspace.activeFileId;
      setWorkspace((prev) => updateFileContent(prev, currentId, newSource));
    },
    [workspace.activeFileId]
  );

  const handleSaveActiveFile = useCallback(() => {
    if (!workspace.activeFileId) return;
    const fileId = workspace.activeFileId;
    setWorkspace((prev) => markFileClean(prev, fileId));
  }, [workspace.activeFileId]);

  const handleRunApp = useCallback(async () => {
    setIsRunningApp(true);
    setLastRunError(null);
    try {
      const res = await postRunApp(activeFile?.content ?? "", activeFile?.name ?? "");
      const status = (res as any).status ?? "ok";
      setLastRunStatus(status);
      setLastRunMessage((res as any).message ?? null);
      setLastRunError((res as any).error ?? null);
      setRunState((prev) => applyRunResponse(prev, res));
      try {
        const trace = await ApiClient.fetchLastTrace();
        setRunState((prev) => applyLastTrace(prev, trace));
      } catch {
        // Ignore trace refresh errors; user can refresh manually.
      }
    } catch (err) {
      setLastRunStatus("error");
      setLastRunMessage(null);
      setLastRunError("Failed to run app");
    } finally {
      setIsRunningApp(false);
    }
  }, [activeFile?.content, activeFile?.name]);

  const handleRefreshRunInfo = useCallback(async () => {
    setIsRefreshingRunInfo(true);
    try {
      const trace = await ApiClient.fetchLastTrace();
      setRunState((prev) => applyLastTrace(prev, trace));
    } finally {
      setIsRefreshingRunInfo(false);
    }
  }, []);

  const handleViewTrace = useCallback((traceId: string) => {
    setSelectedTraceId(traceId);
    setIsTraceDetailOpen(true);
  }, []);

  const handleCloseTraceDetail = useCallback(() => {
    setIsTraceDetailOpen(false);
  }, []);

  const handleRunIDECommand = useCallback(
    async (id: string) => {
      if (id === "ide.saveAndRun") {
        handleSaveActiveFile();
        await handleRunApp();
        return;
      }
      if (id === "ide.openLastTrace") {
        const trace = runState.lastTrace;
        if (trace?.id) {
          handleViewTrace(trace.id);
        }
        return;
      }
      if (id === "ide.runDiagnostics") {
        setDiagnosticsRequestId((prev) => prev + 1);
      }
    },
    [handleRunApp, handleSaveActiveFile, handleViewTrace, runState.lastTrace]
  );

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      const isMacLike = navigator.platform.toLowerCase().includes("mac");
      const isMeta = isMacLike ? event.metaKey : event.ctrlKey;
      if (isMeta && (event.key === "p" || event.key === "P")) {
        event.preventDefault();
        setIsIDEPaletteOpen(true);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  useEffect(() => {
    if (initialTraceId) {
      setSelectedTraceId(initialTraceId);
      setIsTraceDetailOpen(true);
    }
  }, [initialTraceId]);

  useEffect(() => {
    let cancelled = false;
    async function loadExample() {
      if (!initialExampleName || loadedExampleName === initialExampleName) {
        return;
      }
      const loader = exampleLoader ?? fetchExampleSource;
      try {
        const example = await loader(initialExampleName);
        if (cancelled) return;
        const fileId = `example-${example.name}`;
        setWorkspace({
          files: [
            {
              id: fileId,
              name: example.path,
              content: example.source,
              isDirty: false,
              lastCleanContent: example.source,
            },
          ],
          activeFileId: fileId,
        });
        setExampleError(null);
      } catch (err) {
        if (!cancelled) {
          const message = err instanceof Error ? err.message : String(err);
          setExampleError(`Failed to load example '${initialExampleName}': ${message}`);
        }
      } finally {
        if (!cancelled) {
          setLoadedExampleName(initialExampleName);
        }
      }
    }
    loadExample();
    return () => {
      cancelled = true;
    };
  }, [exampleLoader, initialExampleName, loadedExampleName]);

  return (
    <div className="n3-ide-panel">
      <aside className="n3-ide-sidebar-left">
        <FileExplorer
          files={workspace.files}
          activeFileId={workspace.activeFileId}
          onOpenFile={handleOpenFile}
          onCreateFile={handleCreateFile}
          onDeleteFile={handleDeleteFile}
        />
      </aside>
      <div className="n3-ide-main">
        {exampleError && <div className="n3-example-error">{exampleError}</div>}
        <div className="n3-ide-toolbar">
          <button type="button" onClick={handleSaveActiveFile} disabled={!workspace.activeFileId}>
            Save
          </button>
          <button type="button" onClick={handleRunApp} disabled={isRunningApp}>
            {isRunningApp ? "Running..." : "Run app"}
          </button>
          <RunStatus
            isRunning={isRunningApp}
            lastStatus={lastRunStatus}
            lastMessage={lastRunMessage}
            lastError={lastRunError}
          />
        </div>
        <TabBar
          files={workspace.files}
          activeFileId={workspace.activeFileId}
          onSelectFile={handleOpenFile}
          onCloseFile={handleDeleteFile}
        />
        <EditorWithDiagnostics
          key={activeFile?.id ?? "no-file"}
          initialSource={activeFile?.content ?? ""}
          onSourceChange={handleSourceChange}
          externalDiagnosticsRequestId={diagnosticsRequestId}
        />
        <RunOutputPanel
          lastRun={runState.lastRunResponse}
          lastTrace={runState.lastTrace}
          onRefresh={handleRefreshRunInfo}
          isRefreshing={isRefreshingRunInfo}
          onViewTrace={runState.lastTrace ? handleViewTrace : undefined}
        />
        {isTraceDetailOpen && (
          <TraceDetailPanel traceId={selectedTraceId} onClose={handleCloseTraceDetail} />
        )}
        <CommandPalette
          isOpen={isIDEPaletteOpen}
          commands={ideCommands}
          onClose={() => setIsIDEPaletteOpen(false)}
          onRunCommand={(id) => {
            handleRunIDECommand(id);
            setIsIDEPaletteOpen(false);
          }}
        />
      </div>
      <aside className="n3-ide-sidebar-right">
        <IDEPluginsPanel />
      </aside>
    </div>
  );
};
