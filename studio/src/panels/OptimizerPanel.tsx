import React, { useEffect, useState } from "react";
import { ApiClient } from "../api/client";
import { OptimizationSuggestion } from "../api/types";

interface Props {
  client: typeof ApiClient;
}

const OptimizerPanel: React.FC<Props> = ({ client }) => {
  const [suggestions, setSuggestions] = useState<OptimizationSuggestion[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await client.fetchOptimizerSuggestions();
      setSuggestions(res.suggestions);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const runScan = async () => {
    try {
      await client.scanOptimizer();
      setMessage("Scan started");
      await load();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const apply = async (id: string) => {
    try {
      await client.applySuggestion(id);
      setMessage(`Applied ${id}`);
      await load();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const reject = async (id: string) => {
    try {
      await client.rejectSuggestion(id);
      setMessage(`Rejected ${id}`);
      await load();
    } catch (err: any) {
      setError(err.message);
    }
  };

  return (
    <div className="panel" aria-label="optimizer-panel">
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <h3>Optimizer</h3>
        <button onClick={runScan} disabled={loading}>
          Run Scan
        </button>
      </div>
      {error && <div style={{ color: "red" }}>{error}</div>}
      {message && <div style={{ color: "green" }}>{message}</div>}
      {suggestions.length === 0 ? (
        <div>No suggestions yet.</div>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Title</th>
              <th>Kind</th>
              <th>Status</th>
              <th>Severity</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {suggestions.map((s) => (
              <tr key={s.id}>
                <td>{s.title}</td>
                <td>{s.kind}</td>
                <td>{s.status}</td>
                <td>{s.severity}</td>
                <td>
                  <button onClick={() => apply(s.id)} disabled={loading || s.status === "applied"}>
                    Apply
                  </button>
                  <button onClick={() => reject(s.id)} disabled={loading || s.status === "rejected"}>
                    Reject
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

export default OptimizerPanel;
