import React, { useState } from "react";
import { ApiClient } from "../api/client";

interface Props {
  code: string;
  client: typeof ApiClient;
}

const RunnerPanel: React.FC<Props> = ({ code, client }) => {
  const [appName, setAppName] = useState("support");
  const [result, setResult] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await client.runApp(code, appName);
      setResult(res);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel" aria-label="runner-panel">
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <h3>App Runner & UI Preview</h3>
        <input
          value={appName}
          onChange={(e) => setAppName(e.target.value)}
          placeholder="app name"
          style={{ padding: 8, borderRadius: 6, border: "1px solid #e2e8f0" }}
        />
        <button onClick={run} disabled={loading}>
          {loading ? "Running..." : "Run"}
        </button>
      </div>
      {error && <div style={{ color: "red" }}>{error}</div>}
      {result && (
        <div>
          <h4>Entry Page</h4>
          <pre>{JSON.stringify(result.entry_page, null, 2)}</pre>
          <h4>Graph</h4>
          <pre>{JSON.stringify(result.graph, null, 2)}</pre>
        </div>
      )}
    </div>
  );
};

export default RunnerPanel;
