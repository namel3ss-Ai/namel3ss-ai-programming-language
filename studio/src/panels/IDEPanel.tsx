import React, { useCallback, useMemo, useState } from "react";
import { EditorWithDiagnostics } from "../editor/EditorWithDiagnostics";
import { IDEPluginsPanel } from "./IDEPluginsPanel";
import { FileExplorer } from "../components/FileExplorer";
import { TabBar } from "../components/TabBar";
import { RunStatus } from "../components/RunStatus";
import { RunOutputPanel } from "../components/RunOutputPanel";
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

export const IDEPanel: React.FC = () => {
  const [workspace, setWorkspace] = useState<WorkspaceState>(() => createInitialWorkspace());
  const [runState, setRunState] = useState<IDERunState>(() => createInitialRunState());
  const [isRunningApp, setIsRunningApp] = useState(false);
  const [isRefreshingRunInfo, setIsRefreshingRunInfo] = useState(false);
  const [lastRunStatus, setLastRunStatus] = useState<string | null>(null);
  const [lastRunMessage, setLastRunMessage] = useState<string | null>(null);
  const [lastRunError, setLastRunError] = useState<string | null>(null);

  const activeFile = useMemo(() => {
    if (!workspace.activeFileId) return null;
    return workspace.files.find((f) => f.id === workspace.activeFileId) ?? null;
  }, [workspace]);

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
        />
        <RunOutputPanel
          lastRun={runState.lastRunResponse}
          lastTrace={runState.lastTrace}
          onRefresh={handleRefreshRunInfo}
          isRefreshing={isRefreshingRunInfo}
        />
      </div>
      <aside className="n3-ide-sidebar-right">
        <IDEPluginsPanel />
      </aside>
    </div>
  );
};
