import { tokenizeSource } from "./tokenizer";
import type { Token } from "./tokenizer";

export interface EditorState {
  source: string;
  tokens: Token[];
  cursorOffset: number;
}

export function createEditorState(initialSource: string = ""): EditorState {
  const tokens = tokenizeSource(initialSource);
  return {
    source: initialSource,
    tokens,
    cursorOffset: 0,
  };
}

export function updateEditorSource(prev: EditorState, newSource: string): EditorState {
  const tokens = tokenizeSource(newSource);
  const cursorOffset = Math.min(prev.cursorOffset, newSource.length);
  return {
    source: newSource,
    tokens,
    cursorOffset,
  };
}

export function updateEditorCursor(prev: EditorState, newOffset: number): EditorState {
  const offset = Math.max(0, Math.min(newOffset, prev.source.length));
  return {
    ...prev,
    cursorOffset: offset,
  };
}
