import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ConditionList } from "../components/ConditionList";
import type { NormalizedCondition } from "../trace/conditions";

const sample: NormalizedCondition = {
  id: "c1",
  scope: "flow",
  kind: "simple",
  expression: "x > 1",
  result: true,
  taken: true,
};

describe("ConditionList", () => {
  it("renders empty state", () => {
    render(<ConditionList conditions={[]} />);
    expect(screen.getByText(/No conditions evaluated/)).toBeInTheDocument();
  });

  it("renders conditions with badges and result", () => {
    render(<ConditionList conditions={[sample]} />);
    expect(screen.getByText("x > 1")).toBeInTheDocument();
    expect(screen.getByText("FLOW")).toBeInTheDocument();
    expect(screen.getByText("True")).toBeInTheDocument();
  });
});
