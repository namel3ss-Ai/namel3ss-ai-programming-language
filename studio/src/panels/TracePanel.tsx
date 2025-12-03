import React, { useState } from "react";
import { ApiClient } from "../api/client";

interface Props {
  client: typeof ApiClient;
}

const TracePanel: React.FC<Props> = ({ client }) => {
  const [trace, setTrace] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await client.fetchTrace();
      setTrace(res.trace || null);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel" aria-label="trace-panel">
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <h3>Trace Viewer</h3>
        <button onClick={load} disabled={loading}>
          {loading ? "Loading..." : "Refresh"}
        </button>
      </div>
      {error && <div style={{ color: "red" }}>{error}</div>}
      {trace ? <pre>{JSON.stringify(trace, null, 2)}</pre> : <div>No trace yet.</div>}
    </div>
  );
};

export default TracePanel;
