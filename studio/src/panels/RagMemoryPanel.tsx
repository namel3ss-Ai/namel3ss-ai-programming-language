import React, { useState } from "react";
import { ApiClient } from "../api/client";
import { useApi } from "../hooks/useApi";

interface Props {
  client: typeof ApiClient;
}

const RagMemoryPanel: React.FC<Props> = ({ client }) => {
  const { data, loading, error } = useApi(() => client.fetchStudioSummary(), []);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [qError, setQError] = useState<string | null>(null);
  const [qLoading, setQLoading] = useState(false);

  const runQuery = async () => {
    setQLoading(true);
    setQError(null);
    try {
      const res = await client.queryRag("", query);
      setResults(res.results);
    } catch (err: any) {
      setQError(err.message);
    } finally {
      setQLoading(false);
    }
  };

  return (
    <div className="panel" aria-label="rag-memory-panel">
      <h3>RAG & Memory Explorer</h3>
      {loading && <div>Loading...</div>}
      {error && <div style={{ color: "red" }}>{error}</div>}
      {data && (
        <div className="card-grid">
          <div className="card">
            <div style={{ fontSize: 12, color: "#475569" }}>Memory Items</div>
            <div style={{ fontSize: 20, fontWeight: 600 }}>{data.summary.memory_items}</div>
          </div>
          <div className="card">
            <div style={{ fontSize: 12, color: "#475569" }}>RAG Documents</div>
            <div style={{ fontSize: 20, fontWeight: 600 }}>{data.summary.rag_documents}</div>
          </div>
          <div className="card">
            <div style={{ fontSize: 12, color: "#475569" }}>Agents</div>
            <div style={{ fontSize: 20, fontWeight: 600 }}>{data.summary.total_agents}</div>
          </div>
          <div className="card">
            <div style={{ fontSize: 12, color: "#475569" }}>Flows</div>
            <div style={{ fontSize: 20, fontWeight: 600 }}>{data.summary.total_flows}</div>
          </div>
        </div>
      )}
      <div style={{ marginTop: 12 }}>
        <h4>Test Query</h4>
        <div style={{ display: "flex", gap: 8 }}>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search text"
            style={{ flex: 1, padding: 8, borderRadius: 6, border: "1px solid #e2e8f0" }}
          />
          <button onClick={runQuery} disabled={qLoading}>
            {qLoading ? "Running..." : "Search"}
          </button>
        </div>
        {qError && <div style={{ color: "red" }}>{qError}</div>}
        {results.length > 0 && (
          <table className="table" style={{ marginTop: 8 }}>
            <thead>
              <tr>
                <th>Text</th>
                <th>Score</th>
                <th>Source</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r, idx) => (
                <tr key={idx}>
                  <td>{r.text.slice(0, 80)}</td>
                  <td>{r.score.toFixed(3)}</td>
                  <td>{r.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

export default RagMemoryPanel;
