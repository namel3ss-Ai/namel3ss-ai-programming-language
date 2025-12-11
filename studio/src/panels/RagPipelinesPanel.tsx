import React, { useEffect, useMemo, useState } from "react";
import { ApiClient } from "../api/client";
import {
  StudioRagPipelineDetailResponse,
  StudioRagPipelineSummary,
  StudioRagPreviewStage,
  StudioRagStage,
} from "../api/types";

interface Props {
  client: typeof ApiClient;
}

const RagPipelinesPanel: React.FC<Props> = ({ client }) => {
  const [pipelines, setPipelines] = useState<StudioRagPipelineSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<StudioRagPipelineDetailResponse["pipeline"] | null>(null);
  const [selectedStage, setSelectedStage] = useState<StudioRagStage | null>(null);
  const [preview, setPreview] = useState<StudioRagPreviewStage[] | null>(null);
  const [query, setQuery] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  const stageLookup = useMemo(() => {
    const map: Record<string, StudioRagStage> = {};
    (detail?.stages || []).forEach((s) => {
      map[s.name] = s;
    });
    return map;
  }, [detail]);

  useEffect(() => {
    (async () => {
      try {
        const res = await client.fetchStudioRagPipelines();
        setPipelines(res.pipelines || []);
        if (res.pipelines && res.pipelines.length > 0) {
          selectPipeline(res.pipelines[0].id);
        }
      } catch (err: any) {
        setError(err.message);
      }
    })();
  }, [client]);

  const selectPipeline = async (id: string) => {
    setSelectedId(id);
    setError(null);
    setLoading(true);
    try {
      const res = await client.fetchStudioRagPipeline(id);
      setDetail(res.pipeline);
      setSelectedStage(res.pipeline.stages?.[0] || null);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const updateStageField = async (field: string, value: any) => {
    if (!selectedId || !selectedStage) return;
    setError(null);
    try {
      const res = await client.updateStudioRagStage(selectedId, selectedStage.name, { [field]: value });
      setDetail(res.pipeline);
      const updated = res.pipeline.stages.find((s: any) => s.name === selectedStage.name) as StudioRagStage | undefined;
      setSelectedStage(updated || selectedStage);
    } catch (err: any) {
      setError(err.message);
    }
  };

  const runPreview = async () => {
    if (!selectedId) return;
    setError(null);
    try {
      const res = await client.previewStudioRagPipeline(selectedId, query);
      setPreview(res.stages || []);
    } catch (err: any) {
      setError(err.message);
    }
  };

  return (
    <div className="panel" aria-label="rag-pipelines-panel">
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <h3>RAG Pipelines</h3>
        {loading && <span>Loading...</span>}
      </div>
      {error && <div style={{ color: "red" }}>{error}</div>}
      <div style={{ display: "flex", gap: "1rem" }}>
        <div style={{ minWidth: 220 }}>
          <h4>Available pipelines</h4>
          <ul>
            {pipelines.map((p) => (
              <li key={p.id}>
                <button
                  onClick={() => selectPipeline(p.id)}
                  style={{ fontWeight: selectedId === p.id ? "bold" : "normal" }}
                >
                  {p.name}
                </button>
              </li>
            ))}
          </ul>
        </div>
        <div style={{ flex: 1 }}>
          {detail ? (
            <>
              <h4>{detail.name}</h4>
              <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
                {(detail.stages || []).map((stage, idx) => (
                  <div
                    key={stage.name || idx}
                    onClick={() => setSelectedStage(stageLookup[stage.name] || stage)}
                    style={{
                      padding: "0.5rem 0.75rem",
                      border: "1px solid #ddd",
                      borderRadius: 6,
                      cursor: "pointer",
                      background: selectedStage?.name === stage.name ? "#eef6ff" : "#fafafa",
                    }}
                  >
                    <div style={{ fontWeight: 600 }}>{stage.name || `stage-${idx}`}</div>
                    <div style={{ fontSize: 12, color: "#555" }}>{stage.type}</div>
                  </div>
                ))}
              </div>
              {selectedStage && (
                <div style={{ marginTop: "1rem" }}>
                  <h4>Stage inspector: {selectedStage.name}</h4>
                  <div style={{ display: "grid", gridTemplateColumns: "200px 1fr", gap: "0.5rem" }}>
                    <label>type</label>
                    <div>{selectedStage.type}</div>
                    <label>top_k</label>
                    <input
                      aria-label="stage-topk"
                      value={selectedStage.top_k ?? ""}
                      onChange={(e) => updateStageField("top_k", e.target.value ? Number(e.target.value) : null)}
                    />
                    <label>vector_store</label>
                    <input
                      value={selectedStage.vector_store ?? ""}
                      onChange={(e) => updateStageField("vector_store", e.target.value || null)}
                    />
                    <label>graph</label>
                    <input value={selectedStage.graph ?? ""} onChange={(e) => updateStageField("graph", e.target.value || null)} />
                    <label>graph_summary</label>
                    <input
                      value={selectedStage.graph_summary ?? ""}
                      onChange={(e) => updateStageField("graph_summary", e.target.value || null)}
                    />
                    <label>ai</label>
                    <input value={selectedStage.ai ?? ""} onChange={(e) => updateStageField("ai", e.target.value || null)} />
                  </div>
                </div>
              )}
              <div style={{ marginTop: "1rem" }}>
                <h4>Preview</h4>
                <div style={{ display: "flex", gap: "0.5rem" }}>
                  <input
                    placeholder="Enter a query to preview"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    style={{ flex: 1 }}
                  />
                  <button onClick={runPreview}>Run preview</button>
                </div>
                {preview && (
                  <ul>
                    {preview.map((st) => (
                      <li key={st.stage}>
                        <strong>{st.stage}</strong>: {st.summary}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </>
          ) : (
            <div>No pipeline selected.</div>
          )}
        </div>
      </div>
    </div>
  );
};

export default RagPipelinesPanel;
