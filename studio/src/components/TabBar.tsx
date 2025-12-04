import React from "react";
import type { WorkspaceFile } from "../ide/workspace";

export interface TabBarProps {
  files: WorkspaceFile[];
  activeFileId: string | null;
  onSelectFile: (fileId: string) => void;
  onCloseFile?: (fileId: string) => void;
  className?: string;
}

export const TabBar: React.FC<TabBarProps> = ({
  files,
  activeFileId,
  onSelectFile,
  onCloseFile,
  className,
}) => {
  return (
    <div className={className ?? "n3-tab-bar"}>
      {files.map((file) => (
        <div key={file.id} className={"n3-tab-item" + (file.id === activeFileId ? " n3-tab-item-active" : "")}>
          <button type="button" className="n3-tab-title" onClick={() => onSelectFile(file.id)}>
            {file.name}
            {file.isDirty ? "*" : ""}
          </button>
          {onCloseFile && (
            <button
              type="button"
              className="n3-tab-close"
              onClick={() => onCloseFile(file.id)}
              aria-label={`Close ${file.name}`}
            >
              ×
            </button>
          )}
        </div>
      ))}
    </div>
  );
};
