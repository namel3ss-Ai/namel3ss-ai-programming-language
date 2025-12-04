import type { Token, TokenType } from "./tokenizer";

export interface HighlightedSpan {
  type: TokenType;
  value: string;
}

export function getTokenClassName(type: TokenType): string {
  switch (type) {
    case "keyword":
      return "n3-token-keyword";
    case "identifier":
      return "n3-token-identifier";
    case "string":
      return "n3-token-string";
    case "number":
      return "n3-token-number";
    case "comment":
      return "n3-token-comment";
    case "punctuation":
      return "n3-token-punctuation";
    case "whitespace":
      return "n3-token-whitespace";
    case "unknown":
    default:
      return "n3-token-unknown";
  }
}

export function tokensToSpans(tokens: Token[]): HighlightedSpan[] {
  return tokens.map((t) => ({
    type: t.type,
    value: t.value,
  }));
}
