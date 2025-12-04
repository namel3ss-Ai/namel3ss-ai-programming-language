import React from "react";

export interface CodeEditorProps {
  value: string;
  onChange: (newValue: string) => void;
  onCursorChange?: (offset: number) => void;
  className?: string;
  readOnly?: boolean;
}

export const CodeEditor: React.FC<CodeEditorProps> = ({
  value,
  onChange,
  onCursorChange,
  className,
  readOnly,
}) => {
  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    if (readOnly) return;
    onChange(e.target.value);
  };

  const handleSelect = (e: React.SyntheticEvent<HTMLTextAreaElement>) => {
    if (!onCursorChange) return;
    const target = e.currentTarget;
    const offset = target.selectionStart ?? 0;
    onCursorChange(offset);
  };

  return (
    <textarea
      className={className ?? "n3-code-editor"}
      value={value}
      onChange={handleChange}
      onSelect={handleSelect}
      onKeyUp={handleSelect}
      readOnly={readOnly}
      spellCheck={false}
    />
  );
};
