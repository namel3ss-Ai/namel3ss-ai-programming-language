import React from "react";
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { HighlightedCodeView } from "../editor/HighlightedCodeView";

describe("HighlightedCodeView", () => {
  it("renders empty pre/code for empty source", () => {
    const { container } = render(<HighlightedCodeView source="" />);
    const pre = container.querySelector("pre");
    const code = container.querySelector("code");
    expect(pre).not.toBeNull();
    expect(code).not.toBeNull();
    expect(code?.textContent).toBe("");
  });

  it("renders spans with appropriate class names for tokens", () => {
    const source = 'app "Demo" # comment';
    const { container } = render(<HighlightedCodeView source={source} />);
    const spans = container.querySelectorAll("span");
    expect(spans.length).toBeGreaterThan(0);

    const spanList = Array.from(spans);
    expect(spanList.some((el) => el.className.includes("n3-token-keyword"))).toBe(true);
    expect(spanList.some((el) => el.className.includes("n3-token-string"))).toBe(true);
    expect(spanList.some((el) => el.className.includes("n3-token-comment"))).toBe(true);
  });
});
