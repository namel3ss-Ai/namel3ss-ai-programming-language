export interface WorkspaceFile {
  id: string;
  name: string;
  content: string;
  isDirty: boolean;
  lastCleanContent: string;
}

export interface WorkspaceState {
  files: WorkspaceFile[];
  activeFileId: string | null;
}

export function createInitialWorkspace(): WorkspaceState {
  const initialFile: WorkspaceFile = {
    id: "file-1",
    name: "main.ai",
    content: "",
    isDirty: false,
    lastCleanContent: "",
  };
  return {
    files: [initialFile],
    activeFileId: initialFile.id,
  };
}

export function setActiveFile(state: WorkspaceState, fileId: string): WorkspaceState {
  if (!state.files.some((f) => f.id === fileId)) {
    return state;
  }
  if (state.activeFileId === fileId) {
    return state;
  }
  return {
    ...state,
    activeFileId: fileId,
  };
}

export function createFile(state: WorkspaceState): WorkspaceState {
  const nextIndex = state.files.length + 1;
  const newFile: WorkspaceFile = {
    id: `file-${nextIndex}`,
    name: `untitled-${nextIndex}.ai`,
    content: "",
    isDirty: false,
    lastCleanContent: "",
  };
  return {
    files: [...state.files, newFile],
    activeFileId: newFile.id,
  };
}

export function updateFileContent(state: WorkspaceState, fileId: string, newContent: string): WorkspaceState {
  let found = false;
  const files = state.files.map((file) => {
    if (file.id === fileId) {
      found = true;
      const isDirty = newContent !== file.lastCleanContent;
      return { ...file, content: newContent, isDirty };
    }
    return file;
  });
  if (!found) {
    return state;
  }
  return {
    ...state,
    files,
  };
}

export function markFileClean(state: WorkspaceState, fileId: string): WorkspaceState {
  let found = false;
  const files = state.files.map((file) => {
    if (file.id === fileId) {
      found = true;
      return { ...file, lastCleanContent: file.content, isDirty: false };
    }
    return file;
  });
  if (!found) {
    return state;
  }
  return {
    ...state,
    files,
  };
}

export function deleteFile(state: WorkspaceState, fileId: string): WorkspaceState {
  const remaining = state.files.filter((f) => f.id !== fileId);
  if (remaining.length === 0) {
    return createInitialWorkspace();
  }
  let activeFileId = state.activeFileId;
  if (activeFileId === fileId) {
    activeFileId = remaining[0].id;
  }
  return {
    files: remaining,
    activeFileId,
  };
}
