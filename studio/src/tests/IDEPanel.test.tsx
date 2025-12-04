import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { IDEPanel } from "../panels/IDEPanel";
import * as apiClient from "../api/client";

describe("IDEPanel", () => {
  const originalPlatform = window.navigator.platform;
  const setPlatform = (value: string) =>
    Object.defineProperty(window.navigator, "platform", {
      value,
      configurable: true,
    });

  beforeEach(() => {
    vi.resetAllMocks();
    vi.spyOn(apiClient.ApiClient, "fetchPlugins").mockResolvedValue([] as any);
    vi.spyOn(apiClient.ApiClient, "fetchLastTrace").mockResolvedValue(null as any);
    setPlatform("Win32");
  });

  afterEach(() => {
    setPlatform(originalPlatform);
  });

  it("renders editor and plugin panel", async () => {
    render(<IDEPanel />);

    expect(await screen.findByText("No plugins loaded.")).toBeInTheDocument();
    expect(screen.getByText("Run diagnostics")).toBeInTheDocument();
    expect(screen.getByText("Format")).toBeInTheDocument();
    expect(screen.getByText("Templates")).toBeInTheDocument();
  });

  it("keeps per-file content when switching files", async () => {
    render(<IDEPanel />);
    await screen.findByText("No plugins loaded.");

    const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;

    fireEvent.change(textarea, { target: { value: "main content" } });

    const createButton = screen.getByText("+");
    fireEvent.click(createButton);

    const textareaAfterCreate = screen.getByRole("textbox") as HTMLTextAreaElement;
    fireEvent.change(textareaAfterCreate, { target: { value: "untitled content" } });

    const mainFileButton = screen.getAllByText((text) => text.startsWith("main.ai"))[0];
    fireEvent.click(mainFileButton);

    const textareaBack = screen.getByRole("textbox") as HTMLTextAreaElement;
    expect(textareaBack.value).toBe("main content");

    const newFileButton = screen.getAllByText(/untitled-2\.ai/)[0];
    fireEvent.click(newFileButton);

    const textareaNew = screen.getByRole("textbox") as HTMLTextAreaElement;
    expect(textareaNew.value).toBe("untitled content");
  });

  it("marks active tab and file list entry dirty when edited", async () => {
    render(<IDEPanel />);
    await screen.findByText("No plugins loaded.");

    const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: "modified" } });

    const dirtyEntries = screen.getAllByText("main.ai*");
    expect(dirtyEntries.length).toBeGreaterThan(0);
  });

  it("closes a file via tab close", async () => {
    render(<IDEPanel />);
    await screen.findByText("No plugins loaded.");

    fireEvent.click(screen.getByText("+"));

    const closeButtons = screen.getAllByLabelText(/Close/);
    fireEvent.click(closeButtons[1]);

    expect(screen.queryByText(/untitled-2\.ai/)).not.toBeInTheDocument();
    const remainingMain = screen.getAllByText(/main\.ai/);
    expect(remainingMain.length).toBeGreaterThan(0);
  });

  it("Save marks active file clean and clears dirty indicator", async () => {
    render(<IDEPanel />);
    await screen.findByText("No plugins loaded.");

    const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: "modified" } });
    expect(screen.getAllByText("main.ai*").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByText("Save"));

    expect(screen.getAllByText("main.ai").length).toBeGreaterThan(0);
    expect(screen.queryByText(/main\.ai\*/)).toBeNull();
  });

  it("Run app triggers postRunApp and shows OK status", async () => {
    vi.spyOn(apiClient.ApiClient, "fetchLastTrace").mockResolvedValue({ id: "t1" } as any);
    const runSpy = vi
      .spyOn(apiClient, "postRunApp")
      .mockResolvedValue({ status: "ok", message: "App started", error: null } as any);

    render(<IDEPanel />);
    await screen.findByText("No plugins loaded.");

    fireEvent.click(screen.getByText("Run app"));

    expect(runSpy).toHaveBeenCalledTimes(1);
    expect(await screen.findByText("Last run: OK")).toBeInTheDocument();
    expect(screen.getByText("App started")).toBeInTheDocument();
  });

  it("Run app failure shows error status", async () => {
    vi.spyOn(apiClient.ApiClient, "fetchLastTrace").mockResolvedValue({ id: "t1" } as any);
    vi.spyOn(apiClient, "postRunApp").mockRejectedValue(new Error("boom"));

    render(<IDEPanel />);
    await screen.findByText("No plugins loaded.");

    fireEvent.click(screen.getByText("Run app"));

    expect(await screen.findByText("Last run: Error")).toBeInTheDocument();
    expect(screen.getByText("Failed to run app")).toBeInTheDocument();
  });

  it("RunOutputPanel shows last run response after running app", async () => {
    vi.spyOn(apiClient, "postRunApp").mockResolvedValue({
      status: "ok",
      message: "App executed",
      error: null,
    } as any);
    vi.spyOn(apiClient.ApiClient, "fetchLastTrace").mockResolvedValue(null as any);

    render(<IDEPanel />);
    await screen.findByText("No plugins loaded.");

    fireEvent.click(screen.getByText("Run app"));

    expect(await screen.findByText("Status: ok")).toBeInTheDocument();
    expect(screen.getByText("Message: App executed")).toBeInTheDocument();
  });

  it("RunOutputPanel refresh button refetches last trace", async () => {
    vi.spyOn(apiClient, "postRunApp").mockResolvedValue({
      status: "ok",
      message: "App executed",
      error: null,
    } as any);
    const fetchLastTraceMock = vi
      .spyOn(apiClient.ApiClient, "fetchLastTrace")
      .mockResolvedValueOnce(null as any)
      .mockResolvedValueOnce({
        id: "trace-2",
        status: "done",
        kind: "app_run",
        started_at: "2025-01-01T00:01:00Z",
      } as any);

    render(<IDEPanel />);
    await screen.findByText("No plugins loaded.");

    fireEvent.click(screen.getByText("Run app"));

    await screen.findByText("No last trace available.");

    fireEvent.click(screen.getByText("Refresh"));

    expect(await screen.findByText("ID: trace-2")).toBeInTheDocument();
    expect(fetchLastTraceMock).toHaveBeenCalledTimes(2);
  });

  it("opens IDE command palette on Ctrl+P", async () => {
    render(<IDEPanel />);
    await screen.findByText("No plugins loaded.");

    fireEvent.keyDown(window, { key: "p", ctrlKey: true });

    expect(screen.getByText("Save & Run current file")).toBeInTheDocument();
  });

  it("IDE command 'Save & Run current file' saves and runs app", async () => {
    const runSpy = vi
      .spyOn(apiClient, "postRunApp")
      .mockResolvedValue({ status: "ok", message: "App executed", error: null } as any);

    render(<IDEPanel />);
    await screen.findByText("No plugins loaded.");

    const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: "modified" } });
    expect(screen.getAllByText("main.ai*").length).toBeGreaterThan(0);

    fireEvent.keyDown(window, { key: "p", ctrlKey: true });
    fireEvent.mouseDown(screen.getByText("Save & Run current file"));

    await screen.findByText("Last run: OK");
    expect(runSpy).toHaveBeenCalledTimes(1);
    const mainEntries = await screen.findAllByText("main.ai");
    expect(mainEntries.length).toBeGreaterThan(0);
    expect(screen.queryByText(/main\.ai\*/)).toBeNull();
  });

  it("IDE command 'Open last trace' opens TraceDetailPanel", async () => {
    vi.spyOn(apiClient, "postRunApp").mockResolvedValue({
      status: "ok",
      message: "App executed",
      error: null,
    } as any);
    vi.spyOn(apiClient.ApiClient, "fetchLastTrace").mockResolvedValue({
      id: "trace-xyz",
      status: "done",
      kind: "app_run",
      started_at: "2025-01-01T00:00:00Z",
    } as any);
    vi.spyOn(apiClient.ApiClient, "fetchTraceById").mockResolvedValue({
      id: "trace-xyz",
      status: "done",
      events: [],
    } as any);

    render(<IDEPanel />);
    await screen.findByText("No plugins loaded.");

    fireEvent.click(screen.getByText("Run app"));
    await screen.findByText("ID: trace-xyz");

    fireEvent.keyDown(window, { key: "p", ctrlKey: true });
    fireEvent.mouseDown(screen.getByText("Open last trace"));

    await screen.findByText("Trace Detail");
    expect(apiClient.ApiClient.fetchTraceById).toHaveBeenCalledWith("trace-xyz");
  });

  it("IDE command 'Run diagnostics on current file' triggers diagnostics", async () => {
    vi.spyOn(apiClient, "postDiagnostics").mockResolvedValue({
      diagnostics: [
        {
          code: "N3-001",
          severity: "error",
          message: "Example diagnostics issue",
          range: { start: { line: 0, column: 0 }, end: { line: 0, column: 5 } },
        },
      ],
      summary: { errors: 1 },
      success: false,
    } as any);

    render(<IDEPanel />);
    await screen.findByText("No plugins loaded.");

    fireEvent.keyDown(window, { key: "p", ctrlKey: true });
    fireEvent.mouseDown(screen.getByText("Run diagnostics on current file"));

    await screen.findByText("Errors: 1");
    expect(apiClient.postDiagnostics).toHaveBeenCalled();
    expect(await screen.findByText("Example diagnostics issue")).toBeInTheDocument();
  });

  it("opens TraceDetailPanel when 'View full trace' is clicked", async () => {
    vi.spyOn(apiClient, "postRunApp").mockResolvedValue({
      status: "ok",
      message: "App executed",
      error: null,
    } as any);
    vi.spyOn(apiClient.ApiClient, "fetchLastTrace").mockResolvedValue({
      id: "trace-1",
      status: "done",
      kind: "app_run",
      started_at: "2025-01-01T00:00:00Z",
    } as any);
    vi.spyOn(apiClient.ApiClient, "fetchTraceById").mockResolvedValue({
      id: "trace-1",
      status: "done",
      events: [],
    } as any);

    render(<IDEPanel />);
    await screen.findByText("No plugins loaded.");

    fireEvent.click(screen.getByText("Run app"));

    await screen.findByText("ID: trace-1");

    fireEvent.click(screen.getByText("View full trace"));

    expect(await screen.findByText("Trace Detail")).toBeInTheDocument();
  });

  it("TraceDetailPanel loads trace detail for selected trace", async () => {
    vi.spyOn(apiClient, "postRunApp").mockResolvedValue({
      status: "ok",
      message: "App executed",
      error: null,
    } as any);
    vi.spyOn(apiClient.ApiClient, "fetchLastTrace").mockResolvedValue({
      id: "trace-2",
      status: "done",
      kind: "app_run",
      started_at: "2025-01-01T00:00:00Z",
    } as any);

    const fetchTraceDetailMock = vi
      .spyOn(apiClient.ApiClient, "fetchTraceById")
      .mockResolvedValue({
        id: "trace-2",
        status: "done",
        events: [{ id: "step-1", kind: "First step", status: "done" }],
      } as any);

    render(<IDEPanel />);
    await screen.findByText("No plugins loaded.");

    fireEvent.click(screen.getByText("Run app"));

    await screen.findByText("ID: trace-2");

    fireEvent.click(screen.getByText("View full trace"));

    expect(fetchTraceDetailMock).toHaveBeenCalledWith("trace-2");
    expect(await screen.findByText("First step (done)")).toBeInTheDocument();
  });
});
