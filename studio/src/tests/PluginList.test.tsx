import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { PluginList } from "../components/PluginList";
import type { PluginMetadata } from "../api/types";

describe("PluginList", () => {
  it("renders empty state when no plugins", () => {
    render(<PluginList plugins={[]} />);
    expect(screen.getByText("No plugins loaded.")).toBeInTheDocument();
  });

  it("renders plugin rows with details", () => {
    const plugins: PluginMetadata[] = [
      {
        id: "example",
        name: "Example Plugin",
        version: "1.0.0",
        description: "Test plugin",
        entrypoints: {},
        tags: ["tag1", "tag2"],
      },
    ];

    render(<PluginList plugins={plugins} />);

    expect(screen.getByText("Example Plugin")).toBeInTheDocument();
    expect(screen.getByText("1.0.0")).toBeInTheDocument();
    expect(screen.getByText("tag1, tag2")).toBeInTheDocument();
    expect(screen.getByText("Test plugin")).toBeInTheDocument();
  });
});
