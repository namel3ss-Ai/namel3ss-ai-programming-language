import React from "react";
import { ApiClient } from "../api/client";
import { useApi } from "../hooks/useApi";

interface Props {
  client: typeof ApiClient;
}

const MetricsPanel: React.FC<Props> = ({ client }) => {
  const { data, loading, error } = useApi(() => client.fetchMetrics(), []);

  return (
    <div className="panel" aria-label="metrics-panel">
      <h3>Metrics Dashboard</h3>
      {loading && <div>Loading...</div>}
      {error && <div style={{ color: "red" }}>{error}</div>}
      {data && (
        <div className="card-grid">
          {Object.entries(data.metrics).map(([k, v]) => (
            <div className="card" key={k}>
              <div style={{ fontSize: 12, color: "#475569" }}>{k}</div>
              <div style={{ fontSize: 20, fontWeight: 600 }}>{String(v)}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default MetricsPanel;
