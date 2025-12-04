import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, fireEvent, screen } from "@testing-library/react";
import { CommandPalette, CommandPaletteItem } from "../components/CommandPalette";

const commands: CommandPaletteItem[] = [
  { id: "format", title: "Format file" },
  { id: "diagnostics", title: "Run diagnostics" },
];

describe("CommandPalette", () => {
  it("renders nothing when closed", () => {
    render(<CommandPalette isOpen={false} onClose={() => {}} commands={commands} onRunCommand={() => {}} />);
    expect(screen.queryByPlaceholderText("Type a command...")).not.toBeInTheDocument();
  });

  it("shows commands and runs selected command on click", () => {
    const onRun = vi.fn();
    render(<CommandPalette isOpen={true} onClose={() => {}} commands={commands} onRunCommand={onRun} />);

    const item = screen.getByText("Format file");
    fireEvent.mouseDown(item);

    expect(onRun).toHaveBeenCalledWith("format");
  });

  it("filters commands by query", () => {
    render(<CommandPalette isOpen={true} onClose={() => {}} commands={commands} onRunCommand={() => {}} />);

    const input = screen.getByPlaceholderText("Type a command...");
    fireEvent.change(input, { target: { value: "format" } });

    expect(screen.getByText("Format file")).toBeInTheDocument();
    expect(screen.queryByText("Run diagnostics")).not.toBeInTheDocument();
  });

  it("supports keyboard navigation and Enter activation", () => {
    const onRun = vi.fn();
    render(<CommandPalette isOpen={true} onClose={() => {}} commands={commands} onRunCommand={onRun} />);

    const palette = screen.getByRole("textbox").parentElement!;

    fireEvent.keyDown(palette, { key: "ArrowDown" });
    fireEvent.keyDown(palette, { key: "Enter" });

    expect(onRun).toHaveBeenCalledWith("diagnostics");
  });
});
