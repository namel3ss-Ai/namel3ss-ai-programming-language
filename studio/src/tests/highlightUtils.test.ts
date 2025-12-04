import { describe, it, expect } from "vitest";
import { tokenizeSource } from "../editor/tokenizer";
import { getTokenClassName, tokensToSpans } from "../editor/highlight";

describe("highlight utilities", () => {
  it("maps token types to class names", () => {
    expect(getTokenClassName("keyword")).toBe("n3-token-keyword");
    expect(getTokenClassName("identifier")).toBe("n3-token-identifier");
    expect(getTokenClassName("string")).toBe("n3-token-string");
    expect(getTokenClassName("number")).toBe("n3-token-number");
    expect(getTokenClassName("comment")).toBe("n3-token-comment");
    expect(getTokenClassName("punctuation")).toBe("n3-token-punctuation");
    expect(getTokenClassName("whitespace")).toBe("n3-token-whitespace");
    expect(getTokenClassName("unknown")).toBe("n3-token-unknown");
  });

  it("converts tokens to spans preserving order and values", () => {
    const source = 'app "Demo" # comment';
    const tokens = tokenizeSource(source);
    const spans = tokensToSpans(tokens);
    expect(spans.length).toBe(tokens.length);
    expect(spans[0].value).toBe(tokens[0].value);
    expect(spans[spans.length - 1].value).toBe(tokens[tokens.length - 1].value);
  });
});
