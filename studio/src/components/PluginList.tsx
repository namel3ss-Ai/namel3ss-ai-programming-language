import React from "react";
import type { PluginMetadata } from "../api/types";

export interface PluginListProps {
  plugins: PluginMetadata[];
  className?: string;
}

export const PluginList: React.FC<PluginListProps> = ({ plugins, className }) => {
  return (
    <div className={className ?? "n3-plugin-list"}>
      {plugins.length === 0 ? (
        <div className="n3-plugin-list-empty">No plugins loaded.</div>
      ) : (
        <table className="n3-plugin-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Version</th>
              <th>Tags</th>
              <th>Description</th>
            </tr>
          </thead>
          <tbody>
            {plugins.map((p) => (
              <tr key={p.id}>
                <td>{p.name || p.id}</td>
                <td>{p.version ?? ""}</td>
                <td>{(p.tags || []).join(", ")}</td>
                <td>{p.description ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};
