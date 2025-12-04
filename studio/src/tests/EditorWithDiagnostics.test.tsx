import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, fireEvent, screen } from "@testing-library/react";
import { EditorWithDiagnostics } from "../editor/EditorWithDiagnostics";
import * as apiClient from "../api/client";
import { TEMPLATES } from "../templates/templates";

const originalPlatform = window.navigator.platform;
const setPlatform = (value: string) =>
  Object.defineProperty(window.navigator, "platform", {
    value,
    configurable: true,
  });

describe("EditorWithDiagnostics", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    setPlatform(originalPlatform);
  });

  it("runs diagnostics and displays results", async () => {
    const mock = vi.spyOn(apiClient, "postDiagnostics").mockResolvedValue({
      diagnostics: [
        {
          code: "N3-001",
          severity: "error",
          message: "Example error",
          range: { start: { line: 0, column: 0 }, end: { line: 0, column: 5 } },
        },
      ],
      summary: { errors: 1 },
      success: false,
    });

    render(<EditorWithDiagnostics initialSource={"app Demo"} />);
    fireEvent.click(screen.getByText("Run diagnostics"));
    expect(mock).toHaveBeenCalledWith("app Demo");
    expect(await screen.findByText("Example error")).toBeInTheDocument();
  });

  it("shows error message when diagnostics call fails", async () => {
    vi.spyOn(apiClient, "postDiagnostics").mockRejectedValueOnce(new Error("boom"));
    render(<EditorWithDiagnostics initialSource={"app Demo"} />);
    fireEvent.click(screen.getByText("Run diagnostics"));
    expect(await screen.findByText("Diagnostics failed")).toBeInTheDocument();
  });

  it("formats source via button and shows 'Formatted' when changes are made", async () => {
    const formatted = "formatted source";
    vi.spyOn(apiClient, "postFmtPreview").mockResolvedValue({
      formatted,
      changes_made: true,
    } as any);
    vi.spyOn(apiClient, "postDiagnostics").mockResolvedValue({
      diagnostics: [],
    } as any);

    render(<EditorWithDiagnostics initialSource={"unformatted"} />);

    const button = screen.getByText("Format");
    fireEvent.click(button);

    await screen.findByText("Formatted");
    expect(apiClient.postFmtPreview).toHaveBeenCalledWith("unformatted");

    const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
    expect(textarea.value).toBe(formatted);
  });

  it("shows 'Already formatted' when formatter makes no changes", async () => {
    vi.spyOn(apiClient, "postFmtPreview").mockResolvedValue({
      formatted: "same",
      changes_made: false,
    } as any);
    vi.spyOn(apiClient, "postDiagnostics").mockResolvedValue({
      diagnostics: [],
    } as any);

    render(<EditorWithDiagnostics initialSource={"same"} />);

    const button = screen.getByText("Format");
    fireEvent.click(button);

    await screen.findByText("Already formatted");
  });

  it("shows 'Formatting failed' when formatter call rejects", async () => {
    vi.spyOn(apiClient, "postFmtPreview").mockRejectedValue(new Error("boom"));
    vi.spyOn(apiClient, "postDiagnostics").mockResolvedValue({
      diagnostics: [],
    } as any);

    render(<EditorWithDiagnostics initialSource={"broken"} />);

    const button = screen.getByText("Format");
    fireEvent.click(button);

    await screen.findByText("Formatting failed");
  });

  it("triggers formatting on Ctrl+S / Cmd+S", async () => {
    setPlatform("Win32");

    const formatted = "formatted via shortcut";
    const fmtSpy = vi.spyOn(apiClient, "postFmtPreview").mockResolvedValue({
      formatted,
      changes_made: true,
    } as any);

    vi.spyOn(apiClient, "postDiagnostics").mockResolvedValue({
      diagnostics: [],
    } as any);

    render(<EditorWithDiagnostics initialSource={"unformatted"} />);

    const container = screen.getByText("Run diagnostics").closest("div")!;
    fireEvent.keyDown(container, {
      key: "s",
      ctrlKey: true,
    });

    await screen.findByText("Formatted");
    expect(fmtSpy).toHaveBeenCalledTimes(1);
  });

  it("opens command palette on Ctrl+K / Cmd+K", () => {
    vi.spyOn(apiClient, "postDiagnostics").mockResolvedValue({
      diagnostics: [],
    } as any);
    vi.spyOn(apiClient, "postFmtPreview").mockResolvedValue({
      formatted: "same",
      changes_made: false,
    } as any);

    setPlatform("Win32");

    render(<EditorWithDiagnostics initialSource={"app Demo"} />);

    const wrapper = screen.getByText("Run diagnostics").closest(".n3-editor-with-diagnostics")!;
    fireEvent.keyDown(wrapper, { key: "k", ctrlKey: true });

    const input = screen.getByPlaceholderText("Type a command...");
    expect(input).toBeInTheDocument();
  });

  it("command palette runs format command", async () => {
    const fmtSpy = vi.spyOn(apiClient, "postFmtPreview").mockResolvedValue({
      formatted: "formatted via palette",
      changes_made: true,
    } as any);

    vi.spyOn(apiClient, "postDiagnostics").mockResolvedValue({
      diagnostics: [],
    } as any);

    setPlatform("Win32");

    render(<EditorWithDiagnostics initialSource={"unformatted"} />);

    const wrapper = screen.getByText("Run diagnostics").closest(".n3-editor-with-diagnostics")!;
    fireEvent.keyDown(wrapper, { key: "k", ctrlKey: true });

    const formatItem = await screen.findByText("Format file");
    fireEvent.mouseDown(formatItem);

    await screen.findByText("Formatted");
    expect(fmtSpy).toHaveBeenCalledTimes(1);
  });

  it("command palette runs diagnostics command", async () => {
    const diagSpy = vi.spyOn(apiClient, "postDiagnostics").mockResolvedValue({
      diagnostics: [
        {
          code: "N3-001",
          message: "Example",
          severity: "error",
          range: {
            start: { line: 0, column: 0 },
            end: { line: 0, column: 5 },
          },
          source: "test",
        },
      ],
      summary: { errors: 1 },
    } as any);

    vi.spyOn(apiClient, "postFmtPreview").mockResolvedValue({
      formatted: "same",
      changes_made: false,
    } as any);

    setPlatform("Win32");

    render(<EditorWithDiagnostics initialSource={"app Demo"} />);

    const wrapper = screen.getByText("Run diagnostics").closest(".n3-editor-with-diagnostics")!;
    fireEvent.keyDown(wrapper, { key: "k", ctrlKey: true });

    const diagItem = await screen.findByText("Run diagnostics", { selector: ".n3-command-title" });
    fireEvent.mouseDown(diagItem);

    await screen.findByText("Errors: 1");
    expect(diagSpy).toHaveBeenCalledTimes(1);
  });

  it("calls onSourceChange when source changes", () => {
    const handleSourceChange = vi.fn();

    render(<EditorWithDiagnostics initialSource={"hello"} onSourceChange={handleSourceChange} />);

    const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: "world" } });

    expect(handleSourceChange).toHaveBeenCalledWith("world");
  });

  it("calls onSourceChange when formatting changes content", async () => {
    const formatted = "formatted";
    vi.spyOn(apiClient, "postFmtPreview").mockResolvedValue({
      formatted,
      changes_made: true,
    } as any);
    vi.spyOn(apiClient, "postDiagnostics").mockResolvedValue({
      diagnostics: [],
    } as any);
    const handleSourceChange = vi.fn();

    render(<EditorWithDiagnostics initialSource={"orig"} onSourceChange={handleSourceChange} />);

    fireEvent.click(screen.getByText("Format"));

    await screen.findByText("Formatted");
    expect(handleSourceChange).toHaveBeenCalledWith(formatted);
  });

  it("runs diagnostics when externalDiagnosticsRequestId increments", async () => {
    vi.spyOn(apiClient, "postDiagnostics").mockResolvedValue({
      diagnostics: [
        {
          code: "N3-001",
          severity: "error",
          message: "Example issue",
          range: { start: { line: 0, column: 0 }, end: { line: 0, column: 5 } },
        },
      ],
      summary: { errors: 1 },
      success: false,
    } as any);

    const { rerender } = render(
      <EditorWithDiagnostics initialSource={"app Demo"} externalDiagnosticsRequestId={0} />
    );

    rerender(<EditorWithDiagnostics initialSource={"app Demo"} externalDiagnosticsRequestId={1} />);

    expect(await screen.findByText("Example issue")).toBeInTheDocument();
  });

  it("loads a template into the editor via TemplateWizard", async () => {
    vi.spyOn(apiClient, "postDiagnostics").mockResolvedValue({
      diagnostics: [],
    } as any);
    vi.spyOn(apiClient, "postFmtPreview").mockResolvedValue({
      formatted: "same",
      changes_made: false,
    } as any);

    render(<EditorWithDiagnostics initialSource={""} />);

    const templatesButton = screen.getByText("Templates");
    fireEvent.click(templatesButton);

    const useButton = await screen.findByText("Use this template");
    fireEvent.click(useButton);

    const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
    expect(textarea.value).toBe(TEMPLATES[0].content);
  });
});
