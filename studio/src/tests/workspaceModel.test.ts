import { describe, it, expect } from "vitest";
import {
  createInitialWorkspace,
  setActiveFile,
  createFile,
  updateFileContent,
  deleteFile,
  markFileClean,
} from "../ide/workspace";

describe("workspace model", () => {
  it("creates initial workspace with one active file", () => {
    const ws = createInitialWorkspace();
    expect(ws.files.length).toBe(1);
    expect(ws.activeFileId).not.toBeNull();
    expect(ws.activeFileId).toBe(ws.files[0].id);
    expect(ws.files[0].isDirty).toBe(false);
    expect(ws.files[0].lastCleanContent).toBe("");
  });

  it("setActiveFile changes active file when id exists", () => {
    let ws = createInitialWorkspace();
    ws = createFile(ws);
    const newActive = ws.files[1].id;

    const updated = setActiveFile(ws, newActive);
    expect(updated.activeFileId).toBe(newActive);
  });

  it("updateFileContent changes content of the specified file", () => {
    const ws = createInitialWorkspace();
    const updated = updateFileContent(ws, ws.files[0].id, "hello");

    expect(updated.files[0].content).toBe("hello");
    expect(updated.files[0].isDirty).toBe(true);
  });

  it("deleteFile removes file and updates active file", () => {
    let ws = createInitialWorkspace();
    ws = createFile(ws);
    const firstId = ws.files[0].id;

    const afterDelete = deleteFile(ws, firstId);
    expect(afterDelete.files.some((f) => f.id === firstId)).toBe(false);
    expect(afterDelete.activeFileId).toBe(afterDelete.files[0].id);

    const single = createInitialWorkspace();
    const afterDeleteOnly = deleteFile(single, single.activeFileId!);
    expect(afterDeleteOnly.files.length).toBe(1);
    expect(afterDeleteOnly.activeFileId).toBe(afterDeleteOnly.files[0].id);
  });

  it("marks file clean and tracks lastCleanContent", () => {
    const ws = createInitialWorkspace();
    const withChange = updateFileContent(ws, ws.files[0].id, "changed");
    const cleaned = markFileClean(withChange, withChange.files[0].id);
    expect(cleaned.files[0].isDirty).toBe(false);
    expect(cleaned.files[0].lastCleanContent).toBe("changed");
  });
});
