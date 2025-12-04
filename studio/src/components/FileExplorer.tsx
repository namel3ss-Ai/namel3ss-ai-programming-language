import React from "react";
import type { WorkspaceFile } from "../ide/workspace";

export interface FileExplorerProps {
  files: WorkspaceFile[];
  activeFileId: string | null;
  onOpenFile: (fileId: string) => void;
  onCreateFile: () => void;
  onDeleteFile: (fileId: string) => void;
  className?: string;
}

export const FileExplorer: React.FC<FileExplorerProps> = ({
  files,
  activeFileId,
  onOpenFile,
  onCreateFile,
  onDeleteFile,
  className,
}) => {
  return (
    <div className={className ?? "n3-file-explorer"}>
      <div className="n3-file-explorer-header">
        <span>Files</span>
        <button type="button" className="n3-file-create-button" onClick={onCreateFile}>
          +
        </button>
      </div>
      <ul className="n3-file-list">
        {files.map((file) => (
          <li
            key={file.id}
            className={"n3-file-item" + (file.id === activeFileId ? " n3-file-item-active" : "")}
          >
            <button type="button" className="n3-file-open-button" onClick={() => onOpenFile(file.id)}>
              {file.name}
              {file.isDirty ? "*" : ""}
            </button>
            <button
              type="button"
              className="n3-file-delete-button"
              onClick={() => onDeleteFile(file.id)}
              aria-label={`Delete ${file.name}`}
            >
              ×
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
};
