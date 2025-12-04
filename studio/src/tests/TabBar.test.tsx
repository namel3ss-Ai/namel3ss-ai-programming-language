import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, fireEvent, screen } from "@testing-library/react";
import { TabBar } from "../components/TabBar";
import type { WorkspaceFile } from "../ide/workspace";

const files: WorkspaceFile[] = [
  { id: "file-1", name: "main.ai", content: "", isDirty: false, lastCleanContent: "" },
  { id: "file-2", name: "other.ai", content: "", isDirty: true, lastCleanContent: "" },
];

describe("TabBar", () => {
  it("renders tabs and marks active one", () => {
    render(<TabBar files={files} activeFileId="file-1" onSelectFile={() => {}} />);

    expect(screen.getByText("main.ai")).toBeInTheDocument();
    const activeTab = screen.getByText("main.ai").closest("div");
    expect(activeTab?.className).toContain("n3-tab-item-active");
  });

  it("calls onSelectFile when tab clicked", () => {
    const onSelect = vi.fn();
    render(<TabBar files={files} activeFileId="file-1" onSelectFile={onSelect} />);

    fireEvent.click(screen.getByText("other.ai*"));
    expect(onSelect).toHaveBeenCalledWith("file-2");
  });

  it("shows '*' on dirty tabs", () => {
    render(<TabBar files={files} activeFileId="file-1" onSelectFile={() => {}} />);
    expect(screen.getByText("other.ai*")).toBeInTheDocument();
  });

  it("calls onCloseFile when close button is clicked", () => {
    const onClose = vi.fn();
    render(<TabBar files={files} activeFileId="file-1" onSelectFile={() => {}} onCloseFile={onClose} />);

    const closeButtons = screen.getAllByLabelText(/Close/);
    fireEvent.click(closeButtons[1]);
    expect(onClose).toHaveBeenCalledWith("file-2");
  });
});
