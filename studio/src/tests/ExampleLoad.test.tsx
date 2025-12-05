import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import App from "../App";
import * as apiClient from "../api/client";
import * as exampleApi from "../api/examples";

describe("Example and trace loading from URL", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.spyOn(apiClient.ApiClient, "fetchPlugins").mockResolvedValue([] as any);
    vi.spyOn(apiClient.ApiClient, "fetchLastTrace").mockResolvedValue(null as any);
  });

  it("loads example source into workspace when example param is set", async () => {
    vi.spyOn(exampleApi, "fetchExampleSource").mockResolvedValue({
      name: "multi_agent_debate",
      path: "examples/multi_agent_debate/multi_agent_debate.ai",
      source: "example source content",
    });

    window.history.pushState({}, "", "/studio?example=multi_agent_debate");

    render(<App />);

    const textarea = await screen.findByDisplayValue("example source content");
    expect(textarea).toBeInTheDocument();
    expect(exampleApi.fetchExampleSource).toHaveBeenCalledWith("multi_agent_debate");
  });

  it("opens trace detail when trace param is set", async () => {
    vi.spyOn(exampleApi, "fetchExampleSource").mockResolvedValue({
      name: "any",
      path: "examples/any.ai",
      source: "",
    });
    vi.spyOn(apiClient.ApiClient, "fetchTraceById").mockResolvedValue({
      id: "trace_abc123",
      status: "done",
      events: [],
    } as any);

    window.history.pushState({}, "", "/studio?trace=trace_abc123");

    render(<App />);

    expect(await screen.findByText("Trace Detail")).toBeInTheDocument();
    expect(apiClient.ApiClient.fetchTraceById).toHaveBeenCalledWith("trace_abc123");
  });
});
