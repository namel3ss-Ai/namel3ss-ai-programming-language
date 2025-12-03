import React from "react";

interface CodeInputProps {
  value: string;
  onChange: (value: string) => void;
}

const CodeInput: React.FC<CodeInputProps> = ({ value, onChange }) => {
  return (
    <div className="panel">
      <h3>Program Source</h3>
      <textarea
        className="code-input"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder='Enter Namel3ss DSL (e.g. app "x": ...)'
      />
    </div>
  );
};

export default CodeInput;
