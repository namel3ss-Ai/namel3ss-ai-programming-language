import React, { useState } from "react";
import { ApiClient } from "../api/client";
import { PluginInfo } from "../api/types";

interface Props {
  client: typeof ApiClient;
}

const PluginsPanel: React.FC<Props> = ({ client }) => {
  const [plugins, setPlugins] = useState<PluginInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await client.fetchPlugins();
      setPlugins(res);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const toggle = async (plugin: PluginInfo, enable: boolean) => {
    setMessage(null);
    try {
      if (enable) {
        await client.loadPlugin(plugin.id);
        setMessage(`Loaded ${plugin.name}`);
      } else {
        await client.unloadPlugin(plugin.id);
        setMessage(`Unloaded ${plugin.name}`);
      }
      await load();
    } catch (err: any) {
      setError(err.message);
    }
  };

  return (
    <div className="panel" aria-label="plugins-panel">
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <h3>Plugins</h3>
        <button onClick={load} disabled={loading}>
          {loading ? "Loading..." : "Refresh"}
        </button>
      </div>
      {error && <div style={{ color: "red" }}>{error}</div>}
      {message && <div style={{ color: "green" }}>{message}</div>}
      {plugins.length === 0 ? (
        <div>No plugins found.</div>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Version</th>
              <th>Compatible</th>
              <th>Loaded</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {plugins.map((p) => (
              <tr key={p.id}>
                <td>{p.name}</td>
                <td>{p.version || "-"}</td>
                <td style={{ color: p.compatible ? "green" : "red" }}>{p.compatible ? "yes" : "no"}</td>
                <td>{p.loaded ? "loaded" : "unloaded"}</td>
                <td>
                  <button onClick={() => toggle(p, !p.loaded)} disabled={loading || !p.compatible}>
                    {p.loaded ? "Unload" : "Load"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};

export default PluginsPanel;
