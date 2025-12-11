import React, { useEffect, useState } from "react";
import { ApiClient } from "../api/client";
import { StudioMacroDetail, StudioMacroSummary } from "../api/types";

interface Props {
  client: typeof ApiClient;
}

const MacroInspectorPanel: React.FC<Props> = ({ client }) => {
  const [macros, setMacros] = useState<StudioMacroSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<StudioMacroDetail["macro"] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  useEffect(() => {
    (async () => {
      try {
        const res = await client.fetchStudioMacros();
        setMacros(res.macros || []);
        if (res.macros && res.macros.length > 0) {
          loadDetail(res.macros[0].id);
        }
      } catch (err: any) {
        setError(err.message);
      }
    })();
  }, [client]);

  const loadDetail = async (id: string) => {
    setSelectedId(id);
    setLoading(true);
    setError(null);
    try {
      const res = await client.fetchStudioMacroDetail(id);
      setDetail(res.macro);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel" aria-label="macro-inspector-panel">
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <h3>Macro Inspector</h3>
        {loading && <span>Loading...</span>}
      </div>
      {error && <div style={{ color: "red" }}>{error}</div>}
      <div style={{ display: "flex", gap: "1rem" }}>
        <div style={{ minWidth: 220 }}>
          <h4>Macro calls</h4>
          <ul>
            {macros.map((m) => (
              <li key={m.id}>
                <button
                  onClick={() => loadDetail(m.id)}
                  style={{ fontWeight: selectedId === m.id ? "bold" : "normal" }}
                >
                  {m.name} {m.source ? `(${m.source})` : ""}
                </button>
              </li>
            ))}
          </ul>
        </div>
        <div style={{ flex: 1 }}>
          {detail ? (
            <>
              <h4>
                {detail.name} {detail.source ? `@ ${detail.source}:${detail.line || 0}` : ""}
              </h4>
              <div style={{ display: "grid", gridTemplateColumns: "180px 1fr", gap: "0.5rem" }}>
                <label>Records</label>
                <div>{(detail.artifacts.records || []).join(", ") || "—"}</div>
                <label>Flows</label>
                <div>{(detail.artifacts.flows || []).join(", ") || "—"}</div>
                <label>Pages</label>
                <div>{(detail.artifacts.pages || []).join(", ") || "—"}</div>
                <label>RAG pipelines</label>
                <div>{(detail.artifacts.rag_pipelines || []).join(", ") || "—"}</div>
                <label>Agents</label>
                <div>{(detail.artifacts.agents || []).join(", ") || "—"}</div>
              </div>
            </>
          ) : (
            <div>Select a macro call to inspect its generated artifacts.</div>
          )}
        </div>
      </div>
    </div>
  );
};

export default MacroInspectorPanel;
