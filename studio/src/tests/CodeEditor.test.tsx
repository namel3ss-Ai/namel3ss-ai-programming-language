import React from "react";
import { render, fireEvent } from "@testing-library/react";
import { vi } from "vitest";
import { CodeEditor } from "../editor/CodeEditor";

describe("CodeEditor", () => {
  it("calls onChange and onCursorChange when typing", () => {
    const handleChange = vi.fn();
    const handleCursor = vi.fn();

    const { getByRole } = render(
      <CodeEditor value="initial" onChange={handleChange} onCursorChange={handleCursor} />
    );

    const textarea = getByRole("textbox") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: "new" } });
    expect(handleChange).toHaveBeenCalledWith("new");

    textarea.selectionStart = 2;
    fireEvent.select(textarea);
    expect(handleCursor).toHaveBeenCalledWith(2);
  });

  it("uses default class when none provided", () => {
    const { getByRole } = render(<CodeEditor value="" onChange={() => {}} />);
    expect(getByRole("textbox").className).toBe("n3-code-editor");
  });
});
