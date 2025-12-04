import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, fireEvent, screen } from "@testing-library/react";
import { FileExplorer } from "../components/FileExplorer";
import type { WorkspaceFile } from "../ide/workspace";

const files: WorkspaceFile[] = [
  { id: "file-1", name: "main.ai", content: "", isDirty: false, lastCleanContent: "" },
  { id: "file-2", name: "other.ai", content: "", isDirty: false, lastCleanContent: "" },
];

describe("FileExplorer", () => {
  it("renders files and highlights active file", () => {
    render(
      <FileExplorer
        files={files}
        activeFileId="file-1"
        onOpenFile={() => {}}
        onCreateFile={() => {}}
        onDeleteFile={() => {}}
      />
    );

    expect(screen.getByText("main.ai")).toBeInTheDocument();
    expect(screen.getByText("other.ai")).toBeInTheDocument();

    const activeItem = screen.getByText("main.ai").closest("li");
    expect(activeItem?.className).toContain("n3-file-item-active");
  });

  it("calls onOpenFile when a file is clicked", () => {
    const onOpen = vi.fn();
    render(
      <FileExplorer
        files={files}
        activeFileId="file-1"
        onOpenFile={onOpen}
        onCreateFile={() => {}}
        onDeleteFile={() => {}}
      />
    );

    fireEvent.click(screen.getByText("other.ai"));
    expect(onOpen).toHaveBeenCalledWith("file-2");
  });

  it("calls onCreateFile when + is clicked", () => {
    const onCreate = vi.fn();
    render(
      <FileExplorer
        files={files}
        activeFileId="file-1"
        onOpenFile={() => {}}
        onCreateFile={onCreate}
        onDeleteFile={() => {}}
      />
    );

    fireEvent.click(screen.getByText("+"));
    expect(onCreate).toHaveBeenCalled();
  });

  it("calls onDeleteFile when delete button is clicked", () => {
    const onDelete = vi.fn();
    render(
      <FileExplorer
        files={files}
        activeFileId="file-1"
        onOpenFile={() => {}}
        onCreateFile={() => {}}
        onDeleteFile={onDelete}
      />
    );

    const deleteButton = screen.getByLabelText("Delete main.ai");
    fireEvent.click(deleteButton);
    expect(onDelete).toHaveBeenCalledWith("file-1");
  });

  it("shows '*' for dirty files", () => {
    const dirtyFiles: WorkspaceFile[] = [
      { id: "file-1", name: "main.ai", content: "", isDirty: false, lastCleanContent: "" },
      { id: "file-2", name: "other.ai", content: "", isDirty: true, lastCleanContent: "" },
    ];
    const noop = () => {};
    render(
      <FileExplorer
        files={dirtyFiles}
        activeFileId={"file-1"}
        onOpenFile={noop}
        onCreateFile={noop}
        onDeleteFile={noop}
      />
    );
    const dirtyButton = screen.getByText("other.ai*");
    expect(dirtyButton).toBeInTheDocument();
  });
});
