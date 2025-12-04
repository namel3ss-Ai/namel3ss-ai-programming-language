export type TokenType =
  | "keyword"
  | "identifier"
  | "string"
  | "number"
  | "comment"
  | "punctuation"
  | "whitespace"
  | "unknown";

export interface Token {
  type: TokenType;
  value: string;
  start: number;
  end: number;
}

const KEYWORDS = new Set([
  "app",
  "page",
  "dataset",
  "flow",
  "agent",
  "rag",
  "index",
  "llm",
  "prompt",
  "chain",
]);

const punctuationChars = new Set(["{", "}", "(", ")", "[", "]", ":", ",", "="]);

export function tokenizeSource(source: string): Token[] {
  const tokens: Token[] = [];
  const length = source.length;
  let i = 0;

  while (i < length) {
    const char = source[i];

    // Whitespace
    if (/\s/.test(char)) {
      const start = i;
      while (i < length && /\s/.test(source[i])) {
        i += 1;
      }
      tokens.push({ type: "whitespace", value: source.slice(start, i), start, end: i });
      continue;
    }

    // Comment (# to end of line)
    if (char === "#") {
      const start = i;
      while (i < length && source[i] !== "\n") {
        i += 1;
      }
      tokens.push({ type: "comment", value: source.slice(start, i), start, end: i });
      continue;
    }

    // String literals
    if (char === `"` || char === "'") {
      const quote = char;
      const start = i;
      i += 1;
      while (i < length && source[i] !== quote) {
        i += 1;
      }
      if (i < length && source[i] === quote) {
        i += 1; // consume closing quote
      }
      const end = i;
      tokens.push({ type: "string", value: source.slice(start, end), start, end });
      continue;
    }

    // Numbers
    if (/[0-9]/.test(char)) {
      const start = i;
      while (i < length && /[0-9]/.test(source[i])) {
        i += 1;
      }
      if (i < length && source[i] === ".") {
        i += 1;
        while (i < length && /[0-9]/.test(source[i])) {
          i += 1;
        }
      }
      tokens.push({ type: "number", value: source.slice(start, i), start, end: i });
      continue;
    }

    // Identifiers / keywords
    if (/[A-Za-z_]/.test(char)) {
      const start = i;
      i += 1;
      while (i < length && /[A-Za-z0-9_]/.test(source[i])) {
        i += 1;
      }
      const value = source.slice(start, i);
      const type: TokenType = KEYWORDS.has(value) ? "keyword" : "identifier";
      tokens.push({ type, value, start, end: i });
      continue;
    }

    // Punctuation
    if (punctuationChars.has(char)) {
      tokens.push({ type: "punctuation", value: char, start: i, end: i + 1 });
      i += 1;
      continue;
    }

    // Unknown single character
    tokens.push({ type: "unknown", value: char, start: i, end: i + 1 });
    i += 1;
  }

  return tokens;
}
