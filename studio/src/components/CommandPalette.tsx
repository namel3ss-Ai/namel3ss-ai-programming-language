import React, { useEffect, useMemo, useState, useCallback } from "react";

export interface CommandPaletteItem {
  id: string;
  title: string;
  description?: string;
}

export interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  commands: CommandPaletteItem[];
  onRunCommand: (id: string) => void;
}

export const CommandPalette: React.FC<CommandPaletteProps> = ({
  isOpen,
  onClose,
  commands,
  onRunCommand,
}) => {
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);

  useEffect(() => {
    if (isOpen) {
      setQuery("");
      setActiveIndex(0);
    }
  }, [isOpen]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return commands;
    return commands.filter((cmd) => {
      const title = cmd.title.toLowerCase();
      const desc = (cmd.description ?? "").toLowerCase();
      return title.includes(q) || desc.includes(q);
    });
  }, [commands, query]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActiveIndex((prev) => (filtered.length === 0 ? 0 : Math.min(prev + 1, filtered.length - 1)));
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setActiveIndex((prev) => (filtered.length === 0 ? 0 : Math.max(prev - 1, 0)));
        return;
      }
      if (e.key === "Enter") {
        e.preventDefault();
        if (filtered.length > 0) {
          const cmd = filtered[activeIndex] ?? filtered[0];
          onRunCommand(cmd.id);
        }
      }
    },
    [filtered, activeIndex, onClose, onRunCommand]
  );

  if (!isOpen) {
    return null;
  }

  return (
    <div className="n3-command-palette-backdrop" onClick={onClose}>
      <div
        className="n3-command-palette"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleKeyDown}
      >
        <input
          autoFocus
          className="n3-command-palette-input"
          placeholder="Type a command..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <ul className="n3-command-palette-list">
          {filtered.map((cmd, idx) => (
            <li
              key={cmd.id}
              className={"n3-command-palette-item" + (idx === activeIndex ? " n3-active" : "")}
              onMouseDown={(e) => {
                e.preventDefault();
                onRunCommand(cmd.id);
              }}
            >
              <div className="n3-command-title">{cmd.title}</div>
              {cmd.description && <div className="n3-command-description">{cmd.description}</div>}
            </li>
          ))}
          {filtered.length === 0 && <li className="n3-command-palette-empty">No commands</li>}
        </ul>
      </div>
    </div>
  );
};
