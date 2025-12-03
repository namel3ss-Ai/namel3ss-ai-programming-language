import React from "react";

interface SidebarProps {
  panels: string[];
  current: string;
  onSelect: (panel: string) => void;
}

const Sidebar: React.FC<SidebarProps> = ({ panels, current, onSelect }) => {
  return (
    <div className="sidebar">
      <h2>Studio</h2>
      {panels.map((panel) => (
        <button
          key={panel}
          className={current === panel ? "active" : ""}
          onClick={() => onSelect(panel)}
        >
          {panel}
        </button>
      ))}
    </div>
  );
};

export default Sidebar;
