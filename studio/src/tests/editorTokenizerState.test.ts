import { describe, it, expect } from "vitest";
import { tokenizeSource } from "../editor/tokenizer";
import { createEditorState, updateEditorCursor, updateEditorSource } from "../editor/state";

describe("tokenizeSource", () => {
  it("tokenizes empty source as empty list", () => {
    expect(tokenizeSource("")).toEqual([]);
  });

  it("tokenizes keywords, identifiers, numbers, and punctuation", () => {
    const source = `app "Demo" {
  page home:
    count = 42
}`;
    const tokens = tokenizeSource(source);
    expect(tokens.some((t) => t.type === "keyword" && t.value === "app")).toBe(true);
    expect(tokens.some((t) => t.type === "number" && t.value === "42")).toBe(true);
    expect(tokens.some((t) => t.type === "punctuation" && (t.value === "{" || t.value === "}"))).toBe(true);
  });

  it("tokenizes comments and strings", () => {
    const source = `# comment
app "Demo"
`;
    const tokens = tokenizeSource(source);
    expect(tokens.some((t) => t.type === "comment" && t.value.includes("# comment"))).toBe(true);
    expect(tokens.some((t) => t.type === "string" && t.value.includes("Demo"))).toBe(true);
  });

  it("does not throw on malformed input", () => {
    let result: ReturnType<typeof tokenizeSource> = [];
    expect(() => {
      result = tokenizeSource('app "unterminated');
    }).not.toThrow();
    expect(Array.isArray(result)).toBe(true);
    expect(result.length).toBeGreaterThan(0);
  });
});

describe("editor state helpers", () => {
  it("createEditorState initializes from source and tokenizes", () => {
    const state = createEditorState("app Demo");
    expect(state.source).toBe("app Demo");
    expect(state.tokens.length).toBeGreaterThan(0);
    expect(state.cursorOffset).toBe(0);
  });

  it("updateEditorSource re-tokenizes and clamps cursor", () => {
    const prev = { ...createEditorState("app Demo"), cursorOffset: 10 };
    const updated = updateEditorSource(prev, "app");
    expect(updated.source).toBe("app");
    expect(updated.tokens.some((t) => t.value === "app")).toBe(true);
    expect(updated.cursorOffset).toBeLessThanOrEqual(updated.source.length);
  });

  it("updateEditorCursor clamps within source bounds", () => {
    const state = createEditorState("app Demo");
    const clampedLow = updateEditorCursor(state, -5);
    const clampedHigh = updateEditorCursor(state, 100);
    expect(clampedLow.cursorOffset).toBe(0);
    expect(clampedHigh.cursorOffset).toBe(state.source.length);
  });
});
