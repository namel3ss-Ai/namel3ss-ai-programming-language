import React, { useState } from "react";
import { ApiClient } from "../api/client";
import { DiagnosticsResponse } from "../api/types";

interface Props {
  code: string;
  client: typeof ApiClient;
}

const DiagnosticsPanel: React.FC<Props> = ({ code, client }) => {
  const [strict, setStrict] = useState(false);
  const [result, setResult] = useState<DiagnosticsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await client.fetchDiagnostics(code, strict);
      setResult(res);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel" aria-label="diagnostics-panel">
      <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
        <h3>Diagnostics</h3>
        <label>
          <input type="checkbox" checked={strict} onChange={(e) => setStrict(e.target.checked)} /> Strict
        </label>
        <button onClick={run} disabled={loading}>
          {loading ? "Running..." : "Run diagnostics"}
        </button>
      </div>
      {error && <div style={{ color: "red" }}>{error}</div>}
      {result && (
        <div>
          <div>
            Errors: {result.summary.error_count} Warnings: {result.summary.warning_count} Strict:{" "}
            {String(result.summary.strict)}
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Severity</th>
                <th>Code</th>
                <th>Category</th>
                <th>Message</th>
                <th>Location</th>
                <th>Hint</th>
              </tr>
            </thead>
            <tbody>
              {result.diagnostics.map((d) => (
                <tr key={`${d.code}-${d.message}`}>
                  <td>{d.severity}</td>
                  <td>{d.code}</td>
                  <td>{d.category}</td>
                  <td>{d.message}</td>
                  <td>{d.location}</td>
                  <td>{d.hint}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default DiagnosticsPanel;
